from __future__ import annotations

import ctypes
import os
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from local_app.runtime import (
    RuntimePaths,
    backup_and_migrate,
    ensure_runtime_config,
    runtime_environment,
)
from local_app.server import LocalServer, LocalServerError


MUTEX_NAME = r'Local\AllForCabalWebLauncher'
ERROR_ALREADY_EXISTS = 183


def prepare_runtime(
    *,
    run_migrations: bool = True,
) -> tuple[RuntimePaths, dict[str, str]]:
    paths = RuntimePaths.for_user()
    config = ensure_runtime_config(paths)
    environment = runtime_environment(paths, config)
    os.environ.update(environment)
    if run_migrations:
        backup_and_migrate(paths, environment)
    return paths, config


class WindowsMutex:
    def __init__(
        self,
        name: str = MUTEX_NAME,
        *,
        kernel32=None,
        last_error: Callable[[], int] = ctypes.get_last_error,
    ) -> None:
        if kernel32 is None:
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel32.CreateMutexW.argtypes = [
                ctypes.c_void_p,
                ctypes.c_bool,
                ctypes.c_wchar_p,
            ]
            kernel32.CreateMutexW.restype = ctypes.c_void_p
            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel32.CloseHandle.restype = ctypes.c_bool
        self._kernel32 = kernel32
        self._handle = kernel32.CreateMutexW(None, False, name)
        if not self._handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self.already_exists = last_error() == ERROR_ALREADY_EXISTS

    def close(self) -> None:
        if self._handle:
            self._kernel32.CloseHandle(self._handle)
            self._handle = None

    def __enter__(self) -> 'WindowsMutex':
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.close()


class LauncherController:
    def __init__(
        self,
        root: tk.Tk,
        server: LocalServer,
        *,
        ask_stop: Callable[[], bool] | None = None,
    ) -> None:
        self.root = root
        self.server = server
        self._closing = False
        self._shutdown_complete = False
        self._messages: queue.Queue[tuple] = queue.Queue()
        self._ask_stop = ask_stop or (
            lambda: messagebox.askyesno(
                'All for Cabal Web',
                'ต้องการปิดโปรแกรมและหยุดเซิร์ฟเวอร์หรือไม่?',
                parent=self.root,
            )
        )

        self.root.title('All for Cabal Web')
        self.root.geometry('460x250')
        self.root.minsize(420, 230)
        self.root.protocol('WM_DELETE_WINDOW', self.request_close)

        frame = ttk.Frame(root, padding=24)
        frame.pack(fill='both', expand=True)
        ttk.Label(
            frame,
            text='All for Cabal Web',
            font=('Segoe UI', 18, 'bold'),
        ).pack(anchor='w')
        ttk.Label(
            frame,
            text='http://127.0.0.1:8000',
        ).pack(anchor='w', pady=(2, 18))

        self.status = tk.StringVar(value='กำลังเตรียมโปรแกรม…')
        ttk.Label(
            frame,
            textvariable=self.status,
            wraplength=400,
        ).pack(anchor='w', fill='x', pady=(0, 20))

        actions = ttk.Frame(frame)
        actions.pack(fill='x', side='bottom')
        self.open_button = ttk.Button(
            actions,
            text='เปิดหน้าเว็บ',
            command=self.open_web,
        )
        self.open_button.pack(side='left')
        self.restart_button = ttk.Button(
            actions,
            text='เริ่มใหม่',
            command=self.restart,
        )
        self.restart_button.pack(side='left', padx=8)
        self.close_button = ttk.Button(
            actions,
            text='ปิดโปรแกรม',
            command=self.request_close,
        )
        self.close_button.pack(side='right')

        self.root.after(100, self._drain_messages)

    def start(self) -> None:
        self._set_controls_enabled(False)
        self._set_status('กำลังเริ่มเซิร์ฟเวอร์…')

        def action():
            result = self.server.ensure_started()
            self.server.open_browser()
            return result

        def ready(result):
            self._set_controls_enabled(True)
            if result == 'reused':
                self._set_status('เปิดหน้าเว็บจากเซิร์ฟเวอร์ที่ทำงานอยู่แล้ว')
            else:
                self._set_status('พร้อมใช้งาน')

        self._run_worker(action, ready)

    def open_web(self) -> None:
        self._set_controls_enabled(False)
        self._set_status('กำลังเปิดหน้าเว็บ…')
        self._run_worker(
            self.server.open_browser,
            lambda _result=None: (
                self._set_controls_enabled(True),
                self._set_status('พร้อมใช้งาน'),
            ),
        )

    def restart(self) -> None:
        self._set_controls_enabled(False)
        self._set_status('กำลังเริ่มเซิร์ฟเวอร์ใหม่…')

        def action():
            self.server.restart()
            self.server.open_browser()

        self._run_worker(
            action,
            lambda _result=None: (
                self._set_controls_enabled(True),
                self._set_status('พร้อมใช้งาน'),
            ),
        )

    def request_close(self) -> None:
        if self._closing:
            return
        if not self._ask_stop():
            return
        self._closing = True
        self._set_controls_enabled(False)
        self._set_status('กำลังปิดโปรแกรม…')
        self._run_worker(self.server.stop, self._finish_close)

    def _finish_close(self) -> None:
        self._shutdown_complete = True
        self.root.destroy()

    def _run_worker(
        self,
        action: Callable,
        on_success: Callable | None = None,
    ) -> None:
        def worker():
            try:
                result = action()
            except Exception as exc:
                self._messages.put(('error', exc))
            else:
                self._messages.put(('success', on_success, result))

        threading.Thread(
            target=worker,
            name='AllForCabalWebAction',
            daemon=True,
        ).start()

    def _drain_messages(self) -> None:
        try:
            while True:
                kind, *payload = self._messages.get_nowait()
                if kind == 'success':
                    callback, result = payload
                    if callback is not None:
                        try:
                            callback(result)
                        except TypeError:
                            callback()
                else:
                    error = payload[0]
                    self._set_controls_enabled(True)
                    self._set_status(str(error))
                    messagebox.showerror(
                        'All for Cabal Web',
                        str(error),
                        parent=self.root,
                    )
        except queue.Empty:
            pass
        if not self._shutdown_complete:
            self.root.after(100, self._drain_messages)

    def _set_controls_enabled(self, enabled: bool) -> None:
        state = 'normal' if enabled else 'disabled'
        self.open_button.configure(state=state)
        self.restart_button.configure(state=state)

    def _set_status(self, text: str) -> None:
        self.status.set(text)


def _show_fatal(message: str) -> None:
    root = tk.Tk()
    root.withdraw()
    try:
        messagebox.showerror('All for Cabal Web', message, parent=root)
    finally:
        root.destroy()


def main() -> int:
    server = None
    try:
        paths, config = prepare_runtime(run_migrations=False)
        with WindowsMutex() as mutex:
            if mutex.already_exists:
                LocalServer(paths, config).open_browser()
                return 0

            environment = runtime_environment(paths, config)
            backup_and_migrate(paths, environment)
            root = tk.Tk()
            server = LocalServer(paths, config)
            controller = LauncherController(root, server)
            controller.start()
            root.mainloop()
        return 0
    except (LocalServerError, OSError, RuntimeError, ValueError) as exc:
        _show_fatal(str(exc))
        return 1
    finally:
        if server is not None:
            server.stop()


if __name__ == '__main__':
    raise SystemExit(main())
