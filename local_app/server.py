from __future__ import annotations

import json
import logging
import socket
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Callable
from logging.handlers import RotatingFileHandler
from typing import Any

import uvicorn

from local_app.runtime import RuntimePaths


LOCAL_HOST = '127.0.0.1'
LOCAL_PORT = 8000
LOCAL_BASE_URL = f'http://{LOCAL_HOST}:{LOCAL_PORT}'
LOCAL_PRODUCT = 'all-for-cabal-local'


class LocalServerError(RuntimeError):
    pass


class PortInUseError(LocalServerError):
    pass


class StartupTimeoutError(LocalServerError):
    pass


class BrowserLaunchError(LocalServerError):
    pass


def _is_local_health(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and payload.get('ok') is True
        and payload.get('product') == LOCAL_PRODUCT
    )


class LocalHttpClient:
    def __init__(self, base_url: str = LOCAL_BASE_URL) -> None:
        self.base_url = base_url.rstrip('/')

    def health(self) -> dict | None:
        try:
            with urllib.request.urlopen(
                self.base_url + '/api/health',
                timeout=0.5,
            ) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except (
            OSError,
            TimeoutError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            urllib.error.URLError,
        ):
            return None
        return payload if isinstance(payload, dict) else None

    def launch(self, secret: str) -> str:
        request = urllib.request.Request(
            self.base_url + '/api/local/launch',
            data=b'',
            headers={'X-AFC-Launcher-Secret': secret},
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except (
            OSError,
            TimeoutError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            urllib.error.URLError,
        ) as exc:
            raise LocalServerError(
                'ไม่สามารถขอสิทธิ์เปิดหน้าเว็บจากโปรแกรมได้'
            ) from exc
        token = payload.get('token') if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token:
            raise LocalServerError(
                'เซิร์ฟเวอร์ส่งสิทธิ์เปิดหน้าเว็บไม่ถูกต้อง'
            )
        return token


class _SecretFilter(logging.Filter):
    def __init__(self, secrets_to_hide: list[str]) -> None:
        super().__init__()
        self._secrets = [value for value in secrets_to_hide if value]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for secret in self._secrets:
            message = message.replace(secret, '[redacted]')
        record.msg = message
        record.args = ()
        return True


def configure_local_logging(
    paths: RuntimePaths,
    config: dict[str, str],
) -> logging.Logger:
    paths.logs.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        paths.logs / 'all-for-cabal-web.log',
        maxBytes=1_000_000,
        backupCount=3,
        encoding='utf-8',
    )
    handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s'
    ))
    handler.addFilter(_SecretFilter(list(config.values())))

    logger = logging.getLogger('all_for_cabal.local')
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    uvicorn_error = logging.getLogger('uvicorn.error')
    uvicorn_error.handlers = [handler]
    uvicorn_error.setLevel(logging.INFO)
    uvicorn_error.propagate = False
    logging.getLogger('uvicorn.access').disabled = True
    return logger


def _default_port_is_open() -> bool:
    try:
        with socket.create_connection(
            (LOCAL_HOST, LOCAL_PORT),
            timeout=0.25,
        ):
            return True
    except OSError:
        return False


def _default_app_factory():
    # Launcher setup applies Local settings and migrations before this import.
    from web.app import create_app

    return create_app()


class LocalServer:
    def __init__(
        self,
        paths: RuntimePaths,
        config: dict[str, str],
        *,
        http: LocalHttpClient | Any | None = None,
        port_is_open: Callable[[], bool] = _default_port_is_open,
        app_factory: Callable[[], Any] = _default_app_factory,
        config_factory: Callable[..., Any] = uvicorn.Config,
        server_factory: Callable[[Any], Any] = uvicorn.Server,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.paths = paths
        self.config = config
        self.http = http or LocalHttpClient()
        self._port_is_open = port_is_open
        self._app_factory = app_factory
        self._config_factory = config_factory
        self._server_factory = server_factory
        self._clock = clock
        self._sleep = sleep
        self._uvicorn_server = None
        self._thread = None
        self._logger = configure_local_logging(paths, config)

    def ensure_started(self) -> str:
        if self._port_is_open():
            if _is_local_health(self.http.health()):
                return 'reused'
            raise PortInUseError(
                'พอร์ต 8000 ถูกใช้งานโดยโปรแกรมอื่น กรุณาปิดโปรแกรมนั้นก่อน'
            )
        self.start()
        return 'started'

    def start(self, timeout: float = 20.0) -> None:
        app = self._app_factory()
        self.application = app
        uvicorn_config = self._config_factory(
            app=app,
            host=LOCAL_HOST,
            port=LOCAL_PORT,
            access_log=False,
            log_config=None,
        )
        self._uvicorn_server = self._server_factory(uvicorn_config)
        self._thread = threading.Thread(
            target=self._uvicorn_server.run,
            name='AllForCabalWebServer',
            daemon=False,
        )
        self._thread.start()
        deadline = self._clock() + timeout
        while self._clock() < deadline:
            if _is_local_health(self.http.health()):
                self._logger.info('local server is ready')
                return
            self._sleep(0.1)
        self.stop()
        raise StartupTimeoutError(
            'เซิร์ฟเวอร์เริ่มไม่สำเร็จภายใน 20 วินาที'
        )

    def open_browser(self) -> str:
        token = self.http.launch(self.config['launcher_secret'])
        url = f'{LOCAL_BASE_URL}/local-start#{token}'
        if webbrowser.open(url) is False:
            raise BrowserLaunchError(
                'เปิดเบราว์เซอร์ไม่สำเร็จ กรุณากดปุ่มเปิดหน้าเว็บอีกครั้ง'
            )
        return url

    def restart(self) -> None:
        self.stop()
        self.start()

    def stop(self) -> None:
        if self._uvicorn_server is not None:
            self._uvicorn_server.should_exit = True
        if self._thread is not None:
            self._thread.join(5)
            if getattr(self._thread, 'is_alive', lambda: False)():
                raise LocalServerError('เซิร์ฟเวอร์ยังไม่ปิด จึงยังอัปเดตไม่ได้ กรุณารอให้งานจบ')
        self._logger.info('local server stopped')

    def pending_update(self):
        application = getattr(self, 'application', None)
        service = getattr(getattr(application, 'state', None), 'local_update', None)
        return service if service and service.install_requested else None

    def install_update(self):
        service = self.pending_update()
        if not service:
            raise LocalServerError('ไม่พบคำขออัปเดตที่พร้อมติดตั้ง')
        service.install_requested = False
        try:
            self.stop()
            service.io.launch_installer(service.package, service.digest, service.release['version'])
        except Exception as exc:
            service.state = 'error'
            service.cancel('เริ่มตัวติดตั้งไม่สำเร็จ กรุณาลองใหม่')
            raise LocalServerError('เริ่มตัวติดตั้งไม่สำเร็จ กรุณากดเริ่มใหม่แล้วลองอัปเดตอีกครั้ง') from exc
