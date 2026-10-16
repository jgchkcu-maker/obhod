from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Target:
    id: str
    service: str
    category: str
    host: str
    path: str = "/"
    kind: str = "https"
    port: int = 443

    @classmethod
    def from_url(cls, url, identifier="captured-ws"):
        parsed = urlsplit(url)
        if parsed.scheme not in {"https", "wss"} or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            raise ValueError("Нужен HTTPS/WSS URL без учётных данных")
        return cls(identifier, "fortnite", "epic-tcp", parsed.hostname,
                   (parsed.path or "/") + ("?" + parsed.query if parsed.query else ""),
                   "websocket" if parsed.scheme == "wss" else "https", parsed.port or 443)


def load_targets(path: Path, services=None, quick=False):
    data = json.loads(path.read_text(encoding="utf-8"))
    records = [Target(**t) for t in data["targets"]]
    if services is not None:
        records = [t for t in records if t.service in services]
    if quick:
        chosen = {"yt-web", "yt-image", "discord", "discord-ws", "epic-account", "epic-lightswitch"}
        records = [t for t in records if t.id in chosen]
    return records

