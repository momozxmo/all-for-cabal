"""Standalone Windows installer helper; bundled separately from the web app."""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
import urllib.request


class WindowsUpdateSystem:
    def ready_to_install(self):
        try:
            with socket.create_connection(('127.0.0.1', 8000), timeout=1):
                return False
        except OSError:
            return True

    def wait_for_parent(self, pid):
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        kernel.OpenProcess.restype = ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        handle = kernel.OpenProcess(0x00100000, False, pid)
        if not handle:
            if ctypes.get_last_error() == 87:  # Parent has already exited.
                return True
            raise RuntimeError('ตรวจการปิดโปรแกรมไม่ได้ กรุณาปิดโปรแกรมแล้วลองใหม่')
        try:
            return kernel.WaitForSingleObject(handle, 120_000) == 0
        finally:
            kernel.CloseHandle(handle)

    def install(self, installer, application):
        return subprocess.run([
            str(installer), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
            '/NOCLOSEAPPLICATIONS', '/DIR=' + str(application.parent),
        ], creationflags=subprocess.CREATE_NO_WINDOW, check=False).returncode

    def open_app(self, application):
        subprocess.Popen([str(application)], cwd=application.parent,
                         creationflags=subprocess.CREATE_NO_WINDOW)

    def wait_for_health(self, version):
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2) as response:
                    data = json.loads(response.read(65536))
                if data.get('ok') and data.get('product') == 'all-for-cabal-local' and data.get('version') == version:
                    return True
            except (OSError, ValueError):
                pass
            time.sleep(1)
        return False


def perform_update(request, system=None):
    """Validate the package, wait for the parent, install, and verify startup."""
    system = system or WindowsUpdateSystem()
    installer = Path(request['installer'])
    application = Path(request['application'])
    version = request['version']
    digest = request['sha256']
    if (not isinstance(version, str) or not re.fullmatch(r'\d{1,5}\.\d{1,5}\.\d{1,5}', version)
            or not re.fullmatch(r'[a-f0-9]{64}', digest)
            or not installer.is_absolute() or not application.is_absolute()
            or application.name != 'All for Cabal Web.exe'
            or installer.name != f'All.for.Cabal.Web.Setup-{version}.exe'
            or not isinstance(request['parent_pid'], int) or request['parent_pid'] <= 0):
        raise RuntimeError('ข้อมูลตัวติดตั้งไม่ถูกต้อง กรุณาดาวน์โหลดใหม่')
    if not system.wait_for_parent(request['parent_pid']):
        raise RuntimeError('โปรแกรมเดิมยังไม่ปิด จึงยังไม่ติดตั้ง กรุณาปิดแล้วลองใหม่')
    if not system.ready_to_install():
        raise RuntimeError('ยังมีโปรแกรมใช้พอร์ต 8000 กรุณาปิดโปรแกรมก่อนลองติดตั้งใหม่')
    with installer.open('rb') as stream:
        actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    if actual != digest:
        raise RuntimeError('ไฟล์ติดตั้งไม่ครบหรือเปลี่ยนไป กรุณาดาวน์โหลดใหม่')
    code = system.install(installer, application)
    if code != 0:
        raise RuntimeError(f'ติดตั้งไม่สำเร็จ (รหัส {code}) กรุณาลองใหม่ ข้อมูลเดิมยังถูกเก็บไว้')
    system.open_app(application)
    if not system.wait_for_health(version):
        raise RuntimeError('ติดตั้งแล้วแต่เปิดโปรแกรมรุ่นใหม่ไม่สำเร็จ กรุณาตรวจโปรแกรมหรือพอร์ต 8000 แล้วลองใหม่')
    return {'state': 'success', 'version': version, 'message': 'อัปเดตสำเร็จ พร้อมใช้งาน'}


def save_result(path, result):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    os.replace(temporary, path)


def main():
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    runtime = Path(os.environ.get('LOCAL_RUNTIME_DIR') or
                   str(Path(os.environ['LOCALAPPDATA']) / 'AllForCabalWeb')).resolve() / 'updates'
    request_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else runtime / 'install-request.json'
    if request_path.parent != runtime or request_path.name != 'install-request.json':
        messagebox.showerror('All for Cabal Update', 'ตำแหน่งคำขออัปเดตไม่ถูกต้อง')
        return 1
    result_path = runtime / 'result.json'
    try:
        request = json.loads(request_path.read_text(encoding='utf-8'))
        if Path(request['installer']).resolve().parent != runtime:
            raise ValueError('ตำแหน่ง Setup ไม่ถูกต้อง')
    except (OSError, ValueError, KeyError):
        messagebox.showerror('All for Cabal Update', 'อ่านคำขออัปเดตไม่ได้ กรุณาเปิดโปรแกรมแล้วลองใหม่')
        return 1
    while True:
        try:
            result = perform_update(request)
        except Exception as exc:
            message = str(exc) if isinstance(exc, RuntimeError) else 'อัปเดตไม่สำเร็จ กรุณาตรวจไฟล์และสิทธิ์ติดตั้งแล้วลองใหม่'
            result = {'state': 'error', 'version': request['version'], 'message': message}
            save_result(result_path, result)
            if messagebox.askretrycancel('All for Cabal Update', message, parent=root):
                continue
            return 1
        save_result(result_path, result)
        root.destroy()
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
