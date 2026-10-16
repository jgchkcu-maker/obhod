from __future__ import annotations

import json
from pathlib import Path

from .strategy import Block, Strategy


class Catalog:
    def __init__(self, root: Path):
        self.strategies = [Strategy.from_dict(json.loads(p.read_text(encoding="utf-8")))
                           for p in sorted((root / "flowseal").glob("*.json"))]
        self.custom = [Block.from_dict(b) for p in sorted((root / "custom").glob("*.json"))
                       for b in json.loads(p.read_text(encoding="utf-8"))["blocks"]]
        self.blocks = {b.id: b for s in self.strategies for b in s.blocks}
        self.blocks.update({b.id: b for b in self.custom})

    def default(self) -> list[Block]:
        if not self.strategies:
            raise RuntimeError("Каталог Flowseal пуст. Запустите scripts/fetch_vendor.py")
        base = next((s for s in self.strategies if s.id == "general"), self.strategies[0])
        chosen = [b for b in base.blocks if b.category not in {"game-tcp", "game-udp"}]
        chosen += [self.blocks[x] for x in ("E2", "T1", "U1") if x in self.blocks]
        return chosen

    def select(self, ids: list[str] | None) -> list[Block]:
        if not ids:
            return self.default()
        missing = set(ids) - self.blocks.keys()
        if missing:
            raise ValueError("В каталоге нет блоков: " + ", ".join(sorted(missing)))
        return [self.blocks[x] for x in ids]

