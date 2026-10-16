from __future__ import annotations

import ipaddress
import json
import re
import threading
import urllib.request
from pathlib import Path

from .paths import Paths, atomic_json

UPSTREAM = "https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/1.10.3/lists/"
UPDATABLE = ("list-general.txt", "list-google.txt", "list-exclude.txt", "ipset-all.txt", "ipset-exclude.txt")
EDITABLE = ("list-general-user.txt", "list-epic-user.txt", "list-exclude-user.txt", "ipset-exclude-user.txt", "ipset-fortnite.txt")


def download(url, limit=8_000_000):
    request = urllib.request.Request(url, headers={"User-Agent": "Obhod/0.1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("Размер ответа превышает лимит")
    return data


def clean_lines(text):
    return [line.split("#", 1)[0].strip() for line in text.splitlines()
            if line.split("#", 1)[0].strip()]


def validate_text(name: str, text: str):
    lines = clean_lines(text)
    if len(lines) > 100000:
        raise ValueError("Слишком большой список")
    for value in lines:
        if name.startswith("ipset-"):
            ipaddress.ip_network(value, strict=False)
        else:
            domain = value.removeprefix("*.").encode("idna").decode("ascii")
            if len(domain) > 253 or "." not in domain or not re.fullmatch(r"[A-Za-z0-9.-]+", domain):
                raise ValueError(f"Некорректный домен: {value}")
    return "\n".join(lines) + ("\n" if lines else "")


class Lists:
    def __init__(self, paths: Paths):
        self.paths = paths
        self.lock = threading.RLock()

    def save(self, name, text):
        if name not in EDITABLE:
            raise ValueError("Этот список не предназначен для ручного редактирования")
        value = validate_text(name, text)
        with self.lock:
            path = self.paths.lists / name
            temp = path.with_suffix(".tmp")
            temp.write_text(value, encoding="utf-8")
            temp.replace(path)
            self.prepare_game()

    def prepare_game(self):
        # An empty winws ipset means ANY. Never produce an empty 'loaded' set.
        with self.lock:
            records = set()
            for name in ("ipset-all.txt", "ipset-fortnite.txt"):
                path = self.paths.lists / name
                if path.exists():
                    records.update(clean_lines(path.read_text(encoding="utf-8-sig")))
            (self.paths.lists / "ipset-game.txt").write_text(
                "\n".join(sorted(records)) + "\n" if records else "203.0.113.113/32\n", encoding="utf-8")

    def update(self):
        # Download and validate everything first; preserve all *-user files.
        fresh = {}
        for name in UPDATABLE:
            value = download(UPSTREAM + name).decode("utf-8-sig")
            if name == "ipset-all.txt" and value.strip() == "203.0.113.113/32":
                value = download(UPSTREAM + name + ".backup").decode("utf-8-sig")
            fresh[name] = validate_text(name, value)
            if not fresh[name]:
                raise ValueError(f"Получен пустой список {name}")
        with self.lock:
            for name, value in fresh.items():
                target = self.paths.lists / name
                if target.exists():
                    target.with_suffix(".txt.previous").write_bytes(target.read_bytes())
                temp = target.with_suffix(".download")
                temp.write_text(value, encoding="utf-8")
                temp.replace(target)
            self.prepare_game()
        return {name: len(clean_lines(value)) for name, value in fresh.items()}

    def learn_ip(self, address: str):
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            return
        with self.lock:
            target = self.paths.lists / "ipset-fortnite.txt"
            existing = set(clean_lines(target.read_text(encoding="utf-8")))
            value = str(ip) + ("/32" if ip.version == 4 else "/128")
            if value not in existing:
                with target.open("a", encoding="utf-8") as file:
                    file.write(value + "\n")
                self.prepare_game()

    def update_aws(self):
        data = json.loads(download("https://ip-ranges.amazonaws.com/ip-ranges.json"))
        if not isinstance(data.get("prefixes"), list):
            raise ValueError("Некорректный ответ AWS")
        atomic_json(self.paths.state / "aws-ranges.json", data)
        return len(data["prefixes"])

    def aws_region(self, address: str):
        path = self.paths.state / "aws-ranges.json"
        if not path.exists():
            return ""
        data = json.loads(path.read_text(encoding="utf-8"))
        ip = ipaddress.ip_address(address)
        key, field = ("prefixes", "ip_prefix") if ip.version == 4 else ("ipv6_prefixes", "ipv6_prefix")
        matches = [(ipaddress.ip_network(p[field]), p["region"]) for p in data.get(key, [])]
        return next((region for network, region in sorted(matches, key=lambda x: -x[0].prefixlen)
                     if ip in network), "")

