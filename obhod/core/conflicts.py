from __future__ import annotations

import psutil

from .winws import hidden_run

SERVICE_NAMES = {"zapret", "goodbyedpi", "winws1", "winws2", "discordfix_zapret"}


def detect_conflicts(owned_pid=None):
    conflicts = []
    for service in psutil.win_service_iter():
        try:
            name = service.name()
            if name.lower() not in SERVICE_NAMES:
                continue
            status = service.status()
            if status != "stopped":
                conflicts.append({"kind": "service", "id": name, "status": status})
        except (psutil.Error, OSError):
            continue
    for process in psutil.process_iter(["name", "pid"]):
        if process.info["pid"] != owned_pid and (process.info["name"] or "").lower() in {"winws.exe", "winws2.exe", "goodbyedpi.exe"}:
            conflicts.append({"kind": "process", "id": process.pid, "name": process.info["name"]})
    return conflicts


def stop_conflict(item):
    if item["kind"] == "service" and item["id"].lower() in SERVICE_NAMES:
        result = hidden_run(["sc.exe", "stop", item["id"]])
        if result.returncode:
            raise RuntimeError(result.stdout)
    elif item["kind"] == "process":
        process = psutil.Process(int(item["id"]))
        if process.name().lower() not in {"winws.exe", "winws2.exe", "goodbyedpi.exe"}:
            raise ValueError("PID уже принадлежит другой программе")
        process.terminate()
        process.wait(timeout=5)
    else:
        raise ValueError("Неизвестный конфликт")

