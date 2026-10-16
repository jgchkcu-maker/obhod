from __future__ import annotations

import subprocess
import time

from .winws import hidden_run

NAME = "obhod"


class ServiceManager:
    def __init__(self, binary):
        self.binary = binary.resolve()

    def status(self):
        import psutil
        # Only query status/binpath: as_dict() also reads the description via QueryServiceConfig2W,
        # which raises FileNotFoundError (WinError 2) on some systems.
        try:
            service = psutil.win_service_get(NAME)
            status = service.status()
        except (psutil.NoSuchProcess, FileNotFoundError):
            return {"name": NAME, "status": "not_installed"}
        except (psutil.Error, OSError):
            return {"name": NAME, "status": "unknown"}
        try:
            binpath = service.binpath()
        except (psutil.Error, OSError):
            binpath = ""
        return {"name": NAME, "status": status, "binpath": binpath}

    def _sc(self, *args):
        result = hidden_run(["sc.exe", *args])
        if result.returncode:
            raise RuntimeError(f"sc.exe {' '.join(args[:2])}: {result.stdout}\n{result.stderr}")
        return result.stdout

    def wait(self, wanted, timeout=12):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.status()["status"] in wanted:
                return
            time.sleep(.2)
        raise RuntimeError("Служба obhod не перешла в ожидаемое состояние")

    def stop(self):
        status = self.status()["status"]
        if status not in {"stopped", "not_installed"}:
            self._sc("stop", NAME)
            self.wait({"stopped", "not_installed"})

    def install(self, argv, start=True):
        command = subprocess.list2cmdline([str(self.binary), *argv])
        previous = self.status()
        self.stop()
        try:
            if previous["status"] == "not_installed":
                self._sc("create", NAME, "binPath=", command, "start=", "auto", "DisplayName=", "Обход · zapret")
                self._sc("description", NAME, "Обход: профили YouTube, Discord и Fortnite")
            else:
                self._sc("config", NAME, "binPath=", command, "start=", "auto")
            if start:
                self._sc("start", NAME)
                self.wait({"running"})
        except Exception:
            if previous.get("binpath"):
                self._sc("config", NAME, "binPath=", previous["binpath"])
                if previous["status"] == "running":
                    self._sc("start", NAME)
            else:
                self._sc("delete", NAME)
            raise

    def start(self):
        if self.status()["status"] != "running":
            self._sc("start", NAME)
            self.wait({"running"})

    def remove(self):
        if self.status()["status"] != "not_installed":
            self.stop()
            self._sc("delete", NAME)

    def remove_driver(self):
        import psutil
        from .conflicts import detect_conflicts
        if self.status()["status"] == "running" or any(p.info.get("name", "").lower() in {"winws.exe", "winws2.exe"}
                for p in psutil.process_iter(["name"])) or detect_conflicts():
            raise RuntimeError("Сначала остановите обход и наблюдение; WinDivert может использоваться другой программой")
        for name in ("WinDivert", "WinDivert14"):
            query = hidden_run(["sc.exe", "query", name])
            if query.returncode == 0:
                stopped = hidden_run(["sc.exe", "stop", name])
                if stopped.returncode not in (0, 1062):
                    raise RuntimeError(stopped.stdout)
                self._sc("delete", name)

