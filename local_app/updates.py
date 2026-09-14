"""Local update state. Network and installer effects stay at the boundary."""
from __future__ import annotations

import asyncio
import json
import hashlib
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlsplit

from local_app.runtime import resource_root


RELEASE_API = 'https://api.github.com/repos/momozxmo/tool-cabal-local/releases/latest'
RELEASE_DOWNLOAD = 'https://github.com/momozxmo/tool-cabal-local/releases/download/'


class UpdateError(ValueError):
    pass


def asset_url(url: str, *, redirect=False) -> str:
    parts = urlsplit(url)
    allowed = url.startswith(RELEASE_DOWNLOAD)
    if redirect:
        allowed = allowed or parts.hostname == 'release-assets.githubusercontent.com'
    if (not allowed or parts.scheme != 'https' or parts.username or parts.password
            or parts.port not in (None, 443) or parts.fragment):
        raise UpdateError('แหล่งดาวน์โหลดไม่ถูกต้อง')
    return url


class ReleaseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        asset_url(newurl, redirect=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def current_version() -> str:
    return (resource_root() / 'local_app' / 'version.txt').read_text().strip()


def version_tuple(value: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not re.fullmatch(r'v?\d{1,5}\.\d{1,5}\.\d{1,5}', value):
        raise ValueError('รูปแบบเวอร์ชันไม่ถูกต้อง')
    return tuple(int(part) for part in value.removeprefix('v').split('.'))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
    os.replace(temporary, path)


class UpdateIO:
    def launch_installer(self, package, digest, version):
        application = Path(sys.executable).resolve()
        helper = application.parent / 'All for Cabal Update.exe'
        # The helper must survive replacement of the installation directory.
        temporary_helper = package.parent / 'All for Cabal Update.exe'
        shutil.copy2(helper, temporary_helper)
        request_path = package.parent / 'install-request.json'
        write_json(request_path, {'installer': str(package), 'sha256': digest,
                                 'version': version, 'application': str(application),
                                 'parent_pid': os.getpid()})
        write_json(package.parent / 'result.json', {'state': 'pending', 'version': version})
        subprocess.Popen([str(temporary_helper), str(request_path)],
                         creationflags=subprocess.CREATE_NO_WINDOW)

    def asset_chunks(self, url):
        request = urllib.request.Request(asset_url(url), headers={
            'User-Agent': 'AllForCabal-Updater', 'Accept-Encoding': 'identity'})
        opener = urllib.request.build_opener(ReleaseRedirect())
        with opener.open(request, timeout=30) as response:
            asset_url(response.geturl(), redirect=True)
            while chunk := response.read(256 * 1024):
                yield chunk

    def latest_release(self) -> dict:
        request = urllib.request.Request(RELEASE_API, headers={
            'Accept': 'application/vnd.github+json', 'User-Agent': 'AllForCabal-Updater'})
        with urllib.request.urlopen(request, timeout=15) as response:
            content = response.read(2_000_001)
        if len(content) > 2_000_000:
            raise ValueError('ข้อมูล Release ใหญ่เกินไป')
        return json.loads(content)


class LocalUpdate:
    def __init__(self, root: Path, io=None, gate=None, search_busy=None, previews=None):
        self.root = root / 'updates'
        self.io = io or UpdateIO()
        self.version = current_version()
        self.lock = asyncio.Lock()
        self.release = None
        self.state = 'idle'
        self.message = ''
        self.seen = ''
        self.checking = False
        self.downloaded = 0
        self.total = 0
        self.package = None
        self.digest = ''
        self.download_task = None
        self.gate = gate
        self.search_busy = search_busy or (lambda: False)
        self.tabs = {}
        self.preparation = ''
        self.preparation_deadline = 0
        self.previews = previews
        self.install_requested = False
        try:
            self.seen = json.loads((self.root / 'seen.json').read_text())['version']
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def last_attempt(self):
        try:
            result = json.loads((self.root / 'result.json').read_text(encoding='utf-8'))
            target = result['version']
            version_tuple(target)
            outcome = result['state']
            if outcome not in ('success', 'error', 'pending'):
                return None
            if target != self.version:
                return {'state': 'error', 'version': target,
                        'message': 'การอัปเดตครั้งก่อนยังไม่ยืนยันสำเร็จ รุ่นที่เปิดอยู่คือ ' + self.version +
                        ' — ตรวจอัปเดตแล้วกดอัปเดตเพื่อตรวจและดาวน์โหลดไฟล์ใหม่ได้'}
            return {'state': outcome, 'version': target,
                    'message': ('อัปเดตสำเร็จ พร้อมใช้งาน' if outcome == 'success' else
                                'เปิดรุ่นเป้าหมายแล้ว กรุณาตรวจการใช้งานและผลจากตัวติดตั้ง')}
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def status(self):
        if self.preparation and self.state == 'preparing' and time.monotonic() > self.preparation_deadline:
            self.cancel('รอแท็บอื่นนานเกินไป กรุณากลับไปตรวจร่างแล้วกดอัปเดตอีกครั้ง')
        ready = bool(self.tabs) and all(
            t.get('prepared') == self.preparation and t.get('saved') and not t.get('busy')
            and time.monotonic() - t['seen'] < 10
            for t in self.tabs.values()) if self.preparation else False
        return {'supported': True, 'current_version': self.version,
                'state': self.state, 'message': self.message,
                'downloaded': self.downloaded, 'total': self.total,
                'preparation': self.preparation, 'tabs_ready': ready,
                'stale_tabs': [{'id': key, 'page': tab.get('page', '')}
                               for key, tab in self.tabs.items()
                               if time.monotonic() - tab['seen'] >= 10],
                'warnings': [w for t in self.tabs.values() for w in t.get('warnings', [])],
                'preview_count': self.previews.count() if self.previews else 0,
                'busy': bool(self.gate and self.gate.busy) or self.search_busy(),
                'release': self.release, 'checking': self.checking,
                'last_attempt': self.last_attempt()}

    async def check(self):
        async with self.lock:
            if self.checking or self.state not in ('idle', 'available', 'error'):
                return self.status()
            self.checking = True
        try:
            data = await asyncio.to_thread(self.io.latest_release)
            version = data.get('tag_name', '')
            newer = version_tuple(version) > version_tuple(self.version)
            release = None
            if newer and not data.get('draft') and not data.get('prerelease'):
                release = {'version': version.removeprefix('v'),
                           'notes': str(data.get('body') or 'ไม่มีรายละเอียดเพิ่มเติม'),
                           'assets': data.get('assets') or []}
            async with self.lock:
                self.release = release
                self.state = 'available' if release else 'idle'
                self.message = 'มีเวอร์ชันใหม่' if release else 'เป็นเวอร์ชันล่าสุดแล้ว'
        except Exception:
            async with self.lock:
                self.message = 'ตรวจอัปเดตไม่สำเร็จ กรุณาตรวจอินเทอร์เน็ตแล้วลองใหม่'
        finally:
            self.checking = False
        return self.status()

    async def claim_popup(self):
        async with self.lock:
            version = self.release['version'] if self.release else ''
            show = bool(version and version != self.seen)
            if show:
                write_json(self.root / 'seen.json', {'version': version})
                self.seen = version
            return {'show': show}

    async def download(self):
        async with self.lock:
            if (self.gate and self.gate.busy) or self.search_busy():
                raise UpdateError('มีงานกำลังทำ กรุณารอให้เสร็จก่อนอัปเดต')
            if self.state == 'downloading':
                return self.status()
            if self.state == 'ready':
                return self.status()
            if not self.release or self.checking or self.state not in ('available', 'error'):
                raise UpdateError('กรุณาตรวจเวอร์ชันก่อนดาวน์โหลด')
            self.state = 'downloading'
            self.message = 'กำลังดาวน์โหลด Setup…'
            self.downloaded = 0
            self.package = None
            self.download_task = asyncio.create_task(self._download())
        await asyncio.shield(self.download_task)
        return self.status()

    def _fetch_package(self):
        version = self.release['version']
        name = f'All.for.Cabal.Web.Setup-{version}.exe'
        assets = {a.get('name'): a for a in self.release['assets'] if isinstance(a, dict)}
        if name not in assets or name + '.sha256' not in assets:
            raise UpdateError('Release ไม่มี Setup หรือไฟล์ตรวจสอบ กรุณาลองใหม่ภายหลัง')
        executable, checksum = assets[name], assets[name + '.sha256']
        size = executable.get('size')
        if not isinstance(size, int) or not 0 < size <= 2 * 1024**3:
            raise UpdateError('ขนาด Setup ไม่ถูกต้อง')
        expected_url = RELEASE_DOWNLOAD + f'v{version}/'
        for data in (executable, checksum):
            url = data.get('browser_download_url', '')
            asset_url(url)
            if not url.startswith(expected_url):
                raise UpdateError('ไฟล์ดาวน์โหลดไม่ตรงกับเวอร์ชัน')
        raw = bytearray()
        for chunk in self.io.asset_chunks(checksum['browser_download_url']):
            raw.extend(chunk)
            if len(raw) > 4096:
                raise UpdateError('ไฟล์ตรวจสอบไม่ถูกต้อง')
        match = re.fullmatch(r'([0-9a-fA-F]{64})\s+\*?([^\r\n]+)\s*', raw.decode('ascii').strip())
        if not match or match[2] not in (name, f'All for Cabal Web Setup-{version}.exe'):
            raise UpdateError('ไฟล์ตรวจสอบไม่ตรงกับ Setup')
        self.total = size
        self.root.mkdir(parents=True, exist_ok=True)
        partial = self.root / (name + '.part')
        destination = self.root / name
        digest = hashlib.sha256()
        try:
            with partial.open('wb') as stream:
                for chunk in self.io.asset_chunks(executable['browser_download_url']):
                    if self.downloaded + len(chunk) > size:
                        raise UpdateError('ขนาดไฟล์ที่ดาวน์โหลดไม่ตรงกับ Release')
                    stream.write(chunk)
                    digest.update(chunk)
                    self.downloaded += len(chunk)
            if self.downloaded != size or digest.hexdigest() != match[1].lower():
                raise UpdateError('Setup โหลดไม่ครบหรือ checksum ไม่ตรง กรุณาลองใหม่')
            os.replace(partial, destination)
            return destination, digest.hexdigest()
        finally:
            partial.unlink(missing_ok=True)

    async def _download(self):
        try:
            path, digest = await asyncio.to_thread(self._fetch_package)
            async with self.lock:
                self.package, self.digest = path, digest
                self.state = 'ready'
                self.message = 'ดาวน์โหลดและตรวจไฟล์แล้ว พร้อมติดตั้ง'
        except Exception as exc:
            async with self.lock:
                self.state = 'error'
                self.message = str(exc) if isinstance(exc, UpdateError) else 'ดาวน์โหลดไม่สำเร็จ ตรวจอินเทอร์เน็ตและพื้นที่ว่างแล้วลองใหม่'

    def tab(self, data):
        tab_id = data['id']
        if data.get('closed'):
            self.tabs.pop(tab_id, None)
        else:
            self.tabs[tab_id] = dict(data, seen=time.monotonic())
        return self.status()

    def forget_tabs(self, ids, confirmed_closed):
        if self.state in ('preparing', 'installing'):
            raise UpdateError('กรุณายกเลิกการเตรียมติดตั้งก่อนจัดการแท็บ')
        if not confirmed_closed:
            raise UpdateError('ต้องยืนยันว่าบันทึกงานและปิดแท็บเหล่านี้แล้วก่อนนำออก')
        if any(key in self.tabs and time.monotonic() - self.tabs[key]['seen'] < 10 for key in ids):
            raise UpdateError('แท็บกลับมาเชื่อมต่อแล้ว กรุณาตรวจร่างในแท็บนั้นก่อน')
        for key in ids:
            self.tabs.pop(key, None)
        return self.status()

    async def prepare(self):
        async with self.lock:
            if self.state == 'preparing':
                return self.status()
            if self.state not in ('available', 'ready', 'error') or not self.release:
                raise UpdateError('กรุณาตรวจอัปเดตและรอให้ดาวน์โหลดเสร็จก่อน')
            if not self.tabs:
                raise UpdateError('กรุณาเปิดหน้าเครื่องมือก่อนอัปเดต')
            if self.status()['stale_tabs']:
                raise UpdateError('มีแท็บไม่ตอบสนอง กลับไปตรวจร่าง หรือกดจัดการแท็บที่ไม่ตอบสนองเมื่อปิดแท็บแล้ว')
            if self.search_busy() or any(t.get('busy') for t in self.tabs.values()):
                raise UpdateError('มีงานกำลังทำ กรุณารอให้เสร็จก่อนอัปเดต')
            if not self.gate or not self.gate.begin_update():
                raise UpdateError('มีงานกำลังทำ กรุณารอให้เสร็จก่อนอัปเดต')
            self.preparation = secrets.token_urlsafe(24)
            self.preparation_deadline = time.monotonic() + 45
            self.state = 'preparing'
            self.message = 'กำลังเก็บร่างและรอแท็บเครื่องมือทุกแท็บ…'
            return self.status()

    def cancel(self, message='ยกเลิกการอัปเดตแล้ว ใช้งานต่อได้'):
        if self.state == 'installing':
            raise UpdateError('กำลังติดตั้ง กรุณารอผลจากตัวติดตั้ง')
        self.preparation = ''
        if self.gate:
            self.gate.end_update()
        self.state = 'ready' if self.package else ('available' if self.release else 'idle')
        self.message = message
        return self.status()

    async def install(self, token, accept_warnings=False):
        async with self.lock:
            state = self.status()
            if self.state == 'installing':
                return state
            if (self.state != 'preparing' or not token or token != self.preparation
                    or not state['tabs_ready'] or not self.package):
                raise UpdateError('ยังไม่พร้อมติดตั้ง กรุณารอให้ทุกแท็บเก็บร่างสำเร็จ')
            if (state['warnings'] or state['preview_count']) and not accept_warnings:
                raise UpdateError('กรุณาตรวจไฟล์และหน้า Aztek ที่ค้างก่อนยืนยันติดตั้ง')
            self.state = 'installing'
            self.message = 'กำลังตรวจไฟล์และปิดหน้า Aztek ที่โปรแกรมดูแล…'
            try:
                digest = await asyncio.to_thread(file_digest, self.package)
                if digest != self.digest:
                    raise UpdateError('Setup เปลี่ยนหลังดาวน์โหลด กรุณาดาวน์โหลดใหม่')
                if self.previews:
                    await self.previews.close()
                self.install_requested = True
                self.message = 'กำลังปิดโปรแกรมเพื่อติดตั้ง กรุณารอ…'
            except Exception as exc:
                self.state = 'error'
                self.package = None
                self.cancel(str(exc) if isinstance(exc, UpdateError) else 'เตรียมติดตั้งไม่สำเร็จ กรุณาปิดหน้า Aztek ที่ค้างแล้วลองใหม่')
            return self.status()


def file_digest(path):
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
