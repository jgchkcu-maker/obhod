from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import socket
import ssl
import time
from dataclasses import asdict, dataclass
from urllib.parse import quote

from .targets import Target


@dataclass
class ProbeResult:
    target: str
    service: str
    category: str
    kind: str
    status: str
    latency_ms: float = 0
    bytes_received: int = 0
    kbps: float = 0
    detail: str = ""
    address: str = ""
    http_status: int = 0

    def to_dict(self):
        return asdict(self)


class ProbeSuite:
    def __init__(self, concurrency=16, timeout=4.0):
        self.concurrency = concurrency
        self.timeout = timeout
        self.player_target = None

    async def _connect(self, target, tls=None, port=None):
        context = None
        if tls:
            context = ssl.create_default_context()
            if tls != "auto":
                context.minimum_version = tls
                context.maximum_version = tls
            context.set_alpn_protocols(["http/1.1"])
        return await asyncio.wait_for(asyncio.open_connection(
            target.host, port or target.port, ssl=context,
            server_hostname=target.host if context else None,
            ssl_handshake_timeout=self.timeout if context else None), self.timeout)

    async def probe(self, target: Target, kind: str) -> ProbeResult:
        started = time.monotonic()
        result = ProbeResult(target.id, target.service, target.category, kind, "error")
        writer = None
        body = bytearray()
        try:
            tls = {"tls12": ssl.TLSVersion.TLSv1_2, "tls13": ssl.TLSVersion.TLSv1_3}.get(kind)
            if kind in {"freeze", "websocket"}:
                tls = "auto"
            reader, writer = await self._connect(target, tls, 80 if kind == "http" else None)
            peer = writer.get_extra_info("peername")
            result.address = peer[0] if peer else ""
            connected = time.monotonic()
            if kind == "tcp":
                result.status = "ok"
                result.detail = "TCP connect без SNI успешен; это не проверка сервиса"
                return result
            method = "GET" if kind in {"freeze", "websocket"} else "HEAD"
            key = base64.b64encode(b"ObhodProbeKey1234").decode()
            extra = (f"Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
                     if kind == "websocket" else "Connection: close\r\n")
            request = f"{method} {target.path} HTTP/1.1\r\nHost: {target.host}\r\nUser-Agent: Obhod/0.1\r\nAccept: */*\r\nAccept-Encoding: identity\r\n{extra}\r\n"
            writer.write(request.encode("ascii"))
            await asyncio.wait_for(writer.drain(), self.timeout)
            header = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), self.timeout)
            match = re.match(rb"HTTP/1\.[01] (\d{3})", header)
            if not match:
                raise ValueError("Ответ не является HTTP/1.x")
            result.http_status = int(match[1])
            result.latency_ms = round((time.monotonic() - started) * 1000, 1)
            if kind == "websocket":
                expected = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
                headers = dict(line.decode("latin-1").split(":", 1) for line in header.split(b"\r\n")[1:] if b":" in line)
                received = {k.lower(): v.strip() for k, v in headers.items()}
                success = result.http_status == 101 and received.get("sec-websocket-accept") == expected
                result.status = "ok" if success else "unknown"
                result.detail = "WebSocket Upgrade подтверждён" if success else f"HTTP {result.http_status}: Upgrade не подтверждён; возможна авторизация"
            elif kind == "freeze":
                if result.http_status != 200:
                    result.status, result.detail = "unknown", f"HTTP {result.http_status}: тело не подходит для проверки ≥64 КБ"
                    return result
                try:
                    while len(body) < 262144:
                        chunk = await asyncio.wait_for(reader.read(min(32768, 262144 - len(body))), self.timeout)
                        if not chunk:
                            break
                        body.extend(chunk)
                except (asyncio.TimeoutError, ConnectionError):
                    if len(body) < 65536:
                        result.status = "suspected_freeze" if 14000 <= len(body) <= 24000 else "error"
                        result.detail = f"Передача остановилась после {len(body)} байт; требуется повторная проверка"
                        return result
                result.status = "ok" if len(body) >= 65536 else "unknown"
                result.detail = "Получено ≥64 КБ без остановки" if result.status == "ok" else "Тело <64 КБ; проверка заморозки не состоялась"
                result.kbps = round(len(body) * 8 / max(time.monotonic() - connected, .001) / 1000, 1)
                if target.id == "yt-web":
                    self._discover_player(body)
            else:
                result.status = "ok"
                result.detail = f"HTTP {result.http_status}; транспорт доступен, работоспособность API не подтверждена"
        except (OSError, ValueError, asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError) as exc:
            result.detail = f"{type(exc).__name__}: {exc}" or "Таймаут"
        finally:
            result.bytes_received = len(body)
            if not result.latency_ms:
                result.latency_ms = round((time.monotonic() - started) * 1000, 1)
            if writer:
                writer.close()
                try:
                    await asyncio.wait_for(writer.wait_closed(), .2)
                except (OSError, asyncio.TimeoutError):
                    pass
        return result

    def _discover_player(self, body):
        text = body.decode("utf-8", "ignore").replace(r"\/", "/")
        match = re.search(r'(/s/player/[^"\s<>]+?/base\.js)', text)
        if match:
            self.player_target = Target("yt-player-js", "youtube", "google-tcp", "www.youtube.com", match[1])

    async def dns_compare(self, target):
        result = ProbeResult(target.id, target.service, target.category, "dns", "unknown")
        try:
            loop = asyncio.get_running_loop()
            records = await asyncio.wait_for(loop.getaddrinfo(target.host, 443, type=socket.SOCK_STREAM), self.timeout)
            local = sorted({r[4][0] for r in records if r[0] == socket.AF_INET})
            doh_target = Target("doh", "control", "general-tcp", "cloudflare-dns.com",
                                f"/dns-query?name={quote(target.host)}&type=A")
            reader, writer = await self._connect(doh_target, "auto")
            try:
                writer.write((f"GET {doh_target.path} HTTP/1.1\r\nHost: cloudflare-dns.com\r\nAccept: application/dns-json\r\nConnection: close\r\n\r\n").encode())
                await writer.drain()
                header = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), self.timeout)
                if not header.startswith(b"HTTP/1.1 200"):
                    raise ValueError("DoH endpoint недоступен")
                raw = await asyncio.wait_for(reader.read(65536), self.timeout)
                # Read until EOF for small Content-Length JSON responses.
                while len(raw) < 65536:
                    part = await asyncio.wait_for(reader.read(65536 - len(raw)), self.timeout)
                    if not part:
                        break
                    raw += part
                if b"transfer-encoding: chunked" in header.lower():
                    decoded, cursor = bytearray(), 0
                    while True:
                        end = raw.index(b"\r\n", cursor)
                        size = int(raw[cursor:end].split(b";", 1)[0], 16)
                        if size == 0:
                            break
                        cursor = end + 2
                        decoded.extend(raw[cursor:cursor + size])
                        cursor += size + 2
                    raw = bytes(decoded)
                data = json.loads(raw)
            finally:
                writer.close()
            remote = sorted(a["data"] for a in data.get("Answer", []) if a.get("type") == 1)
            result.status = "ok" if set(local) & set(remote) else "different"
            result.detail = f"Системный DNS: {local}; DoH: {remote}. Разные IP у CDN сами по себе не доказывают подмену DNS."
        except (OSError, ValueError, KeyError, asyncio.TimeoutError, asyncio.IncompleteReadError) as exc:
            result.detail = f"Сравнение DNS не выполнено: {exc}"
        return result

    async def run(self, targets, budget=8.0, dns=False, cancel=None, kinds=("tls13", "tls12", "http", "tcp")):
        semaphore = asyncio.Semaphore(self.concurrency)
        records: list[ProbeResult] = []
        async def execute(target, kind):
            async with semaphore:
                if cancel and cancel.is_set():
                    return
                value = await (self.dns_compare(target) if kind == "dns" else self.probe(target, kind))
                records.append(value)
        # Kind-major order: every target gets its TLS probe before any target gets the next kind,
        # so hanging (blocked) hosts early in the list cannot starve the last targets of the budget.
        jobs = [(target, kind) for kind in kinds for target in targets]
        jobs += [(target, "websocket") for target in targets if target.kind == "websocket"]
        # Put the ≥64K YouTube download in the first batch, ahead of optional DNS.
        if any(t.service == "youtube" for t in targets):
            speed = self.player_target or next((t for t in targets if t.id == "yt-web"), None)
            if speed:
                jobs.insert(0, (speed, "freeze"))
        if dns:
            jobs.extend((t, "dns") for t in targets)
        tasks = {asyncio.create_task(execute(t, kind)): (t, kind) for t, kind in jobs}
        started = time.monotonic()
        pending = set(tasks)
        while pending and time.monotonic() - started < budget and not (cancel and cancel.is_set()):
            _, pending = await asyncio.wait(pending, timeout=min(.2, max(.01, budget - (time.monotonic() - started))))
        for task in pending:
            task.cancel()
            target, kind = tasks[task]
            records.append(ProbeResult(target.id, target.service, target.category, kind, "cancelled" if cancel and cancel.is_set() else "timeout", detail="Общий лимит времени прогона"))
        await asyncio.gather(*tasks, return_exceptions=True)
        return records

