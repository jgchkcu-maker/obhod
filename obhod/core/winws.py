from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from pathlib import Path

log = logging.getLogger("obhod.winws")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def hidden_run(argv, **kwargs):
    return subprocess.run(argv, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          creationflags=NO_WINDOW, timeout=kwargs.pop("timeout", 20), **kwargs)


class WinwsRunner:
    def __init__(self, binary: Path):
        self.binary = binary.resolve()
        self.process: subprocess.Popen | None = None
        self.argv: list[str] = []
        self.last_output: list[str] = []
        self.lock = threading.RLock()

    @property
    def running(self):
        return self.process is not None and self.process.poll() is None

    def supports_dry_run(self):
        if not self.binary.is_file():
            raise FileNotFoundError("winws.exe отсутствует. Запустите scripts/fetch_vendor.py")
        return b"dry-run" in self.binary.read_bytes()

    def validate(self, argv: list[str]) -> dict:
        if not argv or any(not a.startswith("--") for a in argv):
            raise ValueError("Некорректные аргументы winws")
        # Fail before driver installation if a referenced data file is missing.
        for arg in argv:
            key, _, value = arg.partition("=")
            if key in {"--hostlist", "--hostlist-exclude", "--ipset", "--ipset-exclude"} or (
                    key.startswith("--dpi-desync-") and ("fake-" in key or key.endswith("pattern"))
                    and ("/" in value or "\\" in value)):
                if not Path(value).is_file():
                    raise FileNotFoundError(f"Отсутствует файл профиля: {value}")
        if self.supports_dry_run():
            try:
                result = hidden_run([str(self.binary), *argv, "--dry-run"], cwd=self.binary.parent)
            except OSError as exc:
                if getattr(exc, "winerror", None) == 740:
                    raise PermissionError("winws требует прав администратора даже для --dry-run") from exc
                raise
            output = result.stdout + result.stderr
            if result.returncode:
                raise RuntimeError(f"winws отклонил профиль ({result.returncode}):\n{output[-6000:]}")
            return {"status": "validated", "method": "dry-run", "output": output}
        return {"status": "pending", "method": "startup-check"}

    def _read_output(self, process):
        if not process.stdout:
            return
        for line in process.stdout:
            line = line.rstrip()
            self.last_output.append(line)
            self.last_output = self.last_output[-80:]
            log.info("winws: %s", line)
        process.stdout.close()

    def start(self, argv: list[str]):
        with self.lock:
            self.validate(argv)
            if self.running:
                raise RuntimeError("Сначала остановите текущий процесс winws")
            self.last_output = []
            self.process = subprocess.Popen([str(self.binary), *argv], cwd=self.binary.parent,
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
            self.argv = list(argv)
            threading.Thread(target=self._read_output, args=(self.process,), daemon=True).start()
            time.sleep(1.05)
            if not self.running:
                raise RuntimeError("winws завершился при запуске:\n" + "\n".join(self.last_output[-15:]))
            log.info("Started owned winws pid=%s", self.process.pid)

    def stop(self):
        with self.lock:
            if self.running:
                self.process.terminate()
                try:
                    self.process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=3)
                log.info("Stopped owned winws pid=%s", self.process.pid)
            self.process = None

    def replace(self, argv):
        with self.lock:
            self.validate(argv)
            previous = list(self.argv)
            was_running = self.running
            self.stop()
            try:
                self.start(argv)
            except Exception:
                if was_running and previous:
                    try:
                        self.start(previous)
                    except Exception:
                        log.exception("Не удалось восстановить предыдущий процесс")
                raise

