from __future__ import annotations

import ctypes
import ipaddress
import os
import re
import socket
import winreg
from pathlib import Path

import psutil

from .conflicts import detect_conflicts
from .winws import hidden_run


def is_admin():
    return os.name == "nt" and bool(ctypes.windll.shell32.IsUserAnAdmin())


TUNNEL_ADAPTERS = re.compile(r"tun|tap|wintun|wireguard|warp|vpn|clash|meta tunnel|sing|amnezia|happ", re.I)
FAKE_IP = ipaddress.ip_network("198.18.0.0/15")


def detect_tunnel() -> list[str]:
    """Signs that traffic goes through a VPN/proxy TUN: then zapret and the tuner measure the tunnel, not the ISP."""
    found = []
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo("www.youtube.com", 443, socket.AF_INET)}
        fake = sorted(a for a in addresses if ipaddress.ip_address(a) in FAKE_IP)
        if fake:
            found.append(f"DNS отдаёт поддельные адреса туннеля (youtube.com → {fake[0]})")
    except OSError:
        pass
    adapters = [name for name, stats in psutil.net_if_stats().items() if stats.isup and TUNNEL_ADAPTERS.search(name)]
    if adapters:
        found.append("Активные адаптеры туннеля: " + ", ".join(adapters))
    from .tunnels import find_clients
    clients = find_clients()
    if clients:
        found.append("Запущены VPN/прокси-клиенты: " + ", ".join(c.name for c in clients))
    return found


def diagnose(paths, owned_pid=None):
    results = []
    def add(key, status, title, detail, fix=None):
        results.append(dict(key=key, status=status, title=title, detail=detail, fix=fix))
    add("admin", "ok" if is_admin() else "warning", "Права администратора",
        "Есть" if is_admin() else "Для winws, наблюдения и службы нужен запуск от администратора")
    try:
        bfe = psutil.win_service_get("BFE").status()
    except (psutil.Error, OSError):
        bfe = "unknown"
    add("bfe", "ok" if bfe == "running" else "error", "Base Filtering Engine", bfe, "bfe" if bfe != "running" else None)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Internet Settings") as registry:
            proxy = winreg.QueryValueEx(registry, "ProxyEnable")[0]
            try:
                proxy_server = winreg.QueryValueEx(registry, "ProxyServer")[0]
            except OSError:
                proxy_server = ""
        add("proxy", "warning" if proxy else "ok", "Системный прокси", str(proxy_server) if proxy else "Выключен")
    except OSError as exc:
        add("proxy", "unknown", "Системный прокси", str(exc))
    tcp = hidden_run(["netsh", "interface", "tcp", "show", "global"])
    timestamps = next((x.strip() for x in tcp.stdout.splitlines() if "timestamp" in x.lower() or "временн" in x.lower()), "Статус не распознан; см. полный вывод")
    enabled = bool(re.search(r"enabled|включен|включён", timestamps, re.I))
    add("timestamps", "ok" if enabled else "warning", "TCP timestamps", timestamps, None if enabled else "timestamps")
    suspects = ("adguard", "killer", "intelligence", "connectivity", "checkpoint", "check point", "smartbyte")
    names = [p.info["name"] or "" for p in psutil.process_iter(["name"])]
    found = [name for name in names if any(x in name.lower() for x in suspects)]
    add("software", "warning" if found else "ok", "Программы с сетевыми фильтрами", ", ".join(found) or "Не обнаружены по именам процессов")
    tunnel = detect_tunnel()
    add("vpn", "error" if tunnel else "ok", "VPN / TUN-прокси",
        ("\n".join(tunnel) + "\nВыключите TUN-режим или клиент целиком: иначе обход и автоподбор работают через туннель.")
        if tunnel else "Трафик идёт напрямую через провайдера")
    doh = hidden_run(["netsh", "dns", "show", "encryption"])
    add("doh", "info", "Системный DoH", doh.stdout.strip() or doh.stderr.strip() or "Настройка недоступна в этой версии Windows")
    hosts = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/drivers/etc/hosts"
    try:
        entries = [x for x in hosts.read_text(encoding="utf-8", errors="replace").splitlines()
                   if not x.strip().startswith("#") and re.search(r"youtube|discord|epicgames|fortnite|googlevideo", x, re.I)]
        add("hosts", "warning" if entries else "ok", "Файл hosts", "\n".join(entries) or "Записей для целевых сервисов нет")
    except OSError as exc:
        add("hosts", "unknown", "Файл hosts", str(exc))
    cyrillic = bool(re.search(r"[А-Яа-яЁё]", str(paths.root)))
    add("path", "warning" if cyrillic else "ok", "Путь программы", str(paths.root))
    add("onedrive", "warning" if "onedrive" in str(paths.root).lower() else "ok", "OneDrive", str(paths.root))
    conflicts = detect_conflicts(owned_pid)
    add("conflicts", "warning" if conflicts else "ok", "Другие программы обхода", str(conflicts) if conflicts else "Активных конфликтов не обнаружено")
    for name in ("WinDivert", "WinDivert14"):
        result = hidden_run(["sc.exe", "query", name])
        if result.returncode == 0:
            add("driver-" + name, "info", "Драйвер " + name, result.stdout.strip())
    return results


def fix(key):
    commands = {"bfe": ["sc.exe", "start", "BFE"],
                "timestamps": ["netsh", "interface", "tcp", "set", "global", "timestamps=enabled"]}
    if key not in commands:
        raise ValueError("Для этого пункта автоматического исправления нет")
    result = hidden_run(commands[key])
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout
