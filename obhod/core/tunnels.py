"""Find and close VPN / TUN-proxy clients so traffic goes straight to the ISP (and through zapret)."""
from __future__ import annotations

import ctypes
import logging
import socket
import time
import winreg
from dataclasses import dataclass, field

import psutil

from .winws import hidden_run

log = logging.getLogger("obhod.tunnels")


@dataclass(frozen=True)
class Client:
    name: str
    processes: tuple[str, ...]          # GUI first, so it cannot respawn the core we kill next
    services: tuple[str, ...] = ()


KNOWN = (
    Client("FlClash", ("flclash.exe", "flclashcore.exe"), ("FlClashHelperService",)),
    Client("Happ", ("happ.exe", "happd.exe"), ("HappService",)),
    Client("Clash Verge", ("clash-verge.exe", "verge-mihomo.exe", "verge-mihomo-alpha.exe", "clash-verge-service.exe"),
           ("clash_verge_service",)),
    Client("Clash / mihomo", ("clash-for-windows.exe", "clash.exe", "clash-meta.exe", "mihomo.exe")),
    Client("Hiddify", ("hiddify.exe", "hiddifycli.exe", "hiddify-cli.exe")),
    Client("v2rayN", ("v2rayn.exe", "xray.exe", "v2ray.exe")),
    Client("NekoBox / Throne", ("nekobox.exe", "nekoray.exe", "throne.exe", "nekobox_core.exe", "throne_core.exe")),
    Client("sing-box", ("sing-box.exe",)),
    Client("Karing", ("karing.exe", "karingservice.exe")),
    Client("Cloudflare WARP", ("cloudflare warp.exe", "warp-svc.exe"), ("CloudflareWARP",)),
    Client("AmneziaVPN", ("amneziavpn.exe", "amneziavpn-service.exe"), ("AmneziaVPN-service",)),
    Client("Outline", ("outline.exe", "outlineservice.exe"), ("OutlineService",)),
    Client("WireGuard", ("wireguard.exe",)),
)
# One service per active tunnel; stopping it is the proper way to disconnect.
TUNNEL_SERVICE_PREFIXES = ("WireGuardTunnel$", "AmneziaWGTunnel$")


@dataclass
class Found:
    name: str
    pids: list[int] = field(default_factory=list)
    services: list[str] = field(default_factory=list)

    def describe(self):
        parts = []
        if self.pids:
            parts.append(f"процессов: {len(self.pids)}")
        if self.services:
            parts.append("службы: " + ", ".join(self.services))
        return f"{self.name} ({'; '.join(parts)})"


def _service_running(name):
    try:
        return psutil.win_service_get(name).status() in {"running", "start_pending"}
    except (psutil.Error, OSError):
        return False


def find_clients() -> list[Found]:
    by_name: dict[str, list[int]] = {}
    for process in psutil.process_iter(["name"]):
        name = (process.info["name"] or "").lower()
        if name:
            by_name.setdefault(name, []).append(process.pid)
    found = []
    for client in KNOWN:
        item = Found(client.name, [pid for exe in client.processes for pid in by_name.get(exe, [])],
                     [s for s in client.services if _service_running(s)])
        if item.pids or item.services:
            found.append(item)
    tunnels = []
    for service in psutil.win_service_iter():
        try:
            name = service.name()
            if name.startswith(TUNNEL_SERVICE_PREFIXES) and service.status() == "running":
                tunnels.append(name)
        except (psutil.Error, OSError):
            continue
    if tunnels:
        wireguard = next((f for f in found if f.name == "WireGuard"), None)
        if wireguard is None:
            wireguard = Found("WireGuard")
            found.append(wireguard)
        wireguard.services += tunnels
    return found


def _order(client: Client | None, pids: list[int]):
    names = [p.lower() for p in client.processes] if client else []

    def key(pid):
        try:
            return names.index(psutil.Process(pid).name().lower())
        except (psutil.Error, ValueError):
            return len(names)
    return sorted(pids, key=key)


def _terminate(pid):
    try:
        process = psutil.Process(pid)
        process.terminate()
        process.wait(timeout=5)
    except psutil.NoSuchProcess:
        pass
    except psutil.TimeoutExpired:
        psutil.Process(pid).kill()


def close_clients(items: list[Found]) -> list[str]:
    """Stop services and processes of the given clients. Services keep their startup type."""
    errors = []
    for item in items:
        client = next((c for c in KNOWN if c.name == item.name), None)
        for pid in _order(client, item.pids):
            try:
                _terminate(pid)
            except psutil.Error as exc:
                errors.append(f"{item.name}: не удалось завершить процесс {pid}: {exc}")
        for service in item.services:
            result = hidden_run(["sc.exe", "stop", service])
            if result.returncode not in (0, 1062):  # 1062: already stopped
                errors.append(f"{item.name}: служба {service}: {result.stdout.strip() or result.stderr.strip()}")
        log.info("Закрыт клиент %s", item.describe())
    time.sleep(1.0)
    # Cores spawned by a service may outlive the service stop.
    for item in find_clients():
        if any(item.name == x.name for x in items):
            for pid in item.pids:
                try:
                    _terminate(pid)
                except psutil.Error as exc:
                    errors.append(f"{item.name}: процесс {pid} остался: {exc}")
    return errors


INTERNET_SETTINGS = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"


def _port_open(host, port):
    try:
        with socket.create_connection((host, port), timeout=.5):
            return True
    except OSError:
        return False


def repair_proxy() -> str:
    """Turn off a system proxy left pointing at a dead local port (clients killed without cleanup)."""
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, INTERNET_SETTINGS, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE) as key:
        try:
            enabled = winreg.QueryValueEx(key, "ProxyEnable")[0]
            server = winreg.QueryValueEx(key, "ProxyServer")[0]
        except OSError:
            return ""
        if not enabled:
            return ""
        first = server.split(";")[0].split("=")[-1]
        host, _, port = first.rpartition(":")
        if host.lower() not in {"127.0.0.1", "localhost", "::1", "[::1]"} or not port.isdigit():
            return ""
        if _port_open(host.strip("[]"), int(port)):
            return ""
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
    wininet = ctypes.windll.wininet
    wininet.InternetSetOptionW(None, 39, None, 0)  # INTERNET_OPTION_SETTINGS_CHANGED
    wininet.InternetSetOptionW(None, 37, None, 0)  # INTERNET_OPTION_REFRESH
    log.info("Отключён мёртвый системный прокси %s", server)
    return f"выключен системный прокси {server}, который остался от VPN-клиента"


def make_direct(items: list[Found] | None = None) -> dict:
    """Close tunnel clients, repair proxy, flush DNS. Returns a report for the UI."""
    from .diagnostics import detect_tunnel
    items = find_clients() if items is None else items
    errors = close_clients(items)
    notes = []
    try:
        fixed = repair_proxy()
        if fixed:
            notes.append(fixed)
    except OSError as exc:
        errors.append(f"Системный прокси: {exc}")
    hidden_run(["ipconfig", "/flushdns"])
    notes.append("сброшен кэш DNS")
    for _ in range(10):  # the TUN adapter and fake-ip DNS disappear a moment after the core exits
        remaining = detect_tunnel()
        if not remaining:
            break
        time.sleep(.5)
    return {"closed": [i.describe() for i in items], "notes": notes, "errors": errors, "remaining": remaining}
