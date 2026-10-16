from __future__ import annotations

import json
import os
import shutil
import sys
import threading
from pathlib import Path
from typing import Any


class Paths:
    def __init__(self, root: Path | None = None, state: Path | None = None):
        self.root = (root or (Path(sys.executable).parent if getattr(sys, "frozen", False)
                              else Path(__file__).resolve().parents[2])).resolve()
        frozen = getattr(sys, "frozen", False)
        # Store Python silently redirects writes under %LOCALAPPDATA% into its package sandbox,
        # where winws.exe cannot see them; from sources keep state next to the project.
        default_state = (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Obhod" if frozen
                         else self.root / ".state")
        self.state = (state or Path(os.environ.get("OBHOD_STATE_DIR") or str(default_state))).resolve()
        self.bin = self.root / "bin"
        self.lists = self.state / "lists"
        self.logs = self.state / "logs"
        self.strategies = self.root / "strategies"
        self.reports = self.state / "reports"

    def ensure(self):
        for path in (self.state, self.lists, self.logs, self.reports):
            path.mkdir(parents=True, exist_ok=True)
        for source in (self.root / "lists").glob("*.txt"):
            target = self.lists / source.name
            if not target.exists():
                shutil.copy2(source, target)
        for name in ("list-general-user.txt", "list-exclude-user.txt", "ipset-exclude-user.txt",
                     "list-epic-user.txt", "ipset-fortnite.txt"):
            (self.lists / name).touch(exist_ok=True)

    def variables(self, tcp="1024-65535", udp="1024-65535"):
        return {"BIN": str(self.bin).replace("\\", "/"),
                "LISTS": str(self.lists).replace("\\", "/"),
                "GAME_TCP": tcp, "GAME_UDP": udp}


DEFAULTS = {"services": ["youtube", "discord", "fortnite"], "game_mode": "all",
            "ipset_mode": "loaded", "tcp_ports": "1024-65535", "udp_ports": "1024-65535",
            "theme": "dark", "close_to_tray": True, "autostart": False, "start_minimized": False,
            "profile": None, "profile_name": "Сбалансированный", "attempts": []}


def atomic_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


class State:
    def __init__(self, paths: Paths):
        self.path = paths.state / "state.json"
        self.lock = threading.RLock()
        self.data = dict(DEFAULTS)
        if self.path.exists():
            try:
                saved = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(saved, dict):
                    self.data.update(saved)
            except (OSError, ValueError):
                shutil.copy2(self.path, self.path.with_suffix(".broken.json"))

    def get(self, key, default=None):
        with self.lock:
            return self.data.get(key, default)

    def update(self, **values):
        with self.lock:
            self.data.update(values)
            atomic_json(self.path, self.data)

