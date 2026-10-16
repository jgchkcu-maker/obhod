from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from typing import Iterable

ORDER = ("discord-voice", "discord-media", "yt-quic", "google-tcp", "epic-tcp",
         "general-tcp", "ipset-udp", "ipset-tcp", "game-tcp", "game-udp")
SERVICE_CATEGORIES = {
    "youtube": {"yt-quic", "google-tcp"},
    "discord": {"discord-voice", "discord-media", "general-tcp"},
    "fortnite": {"epic-tcp", "game-tcp", "game-udp", "ipset-tcp", "ipset-udp"},
}
PLACEHOLDER = re.compile(r"\$\{([A-Z_]+)\}")


def resolve(value: str, variables: dict[str, str]) -> str:
    def sub(match):
        if match[1] not in variables:
            raise ValueError(f"Неизвестная переменная {match[0]}")
        return variables[match[1]]
    return PLACEHOLDER.sub(sub, value)


def port_intervals(spec: str, minimum=1) -> list[tuple[int, int]]:
    result = []
    for piece in spec.split(","):
        if not re.fullmatch(r"\d+(?:-\d+)?", piece.strip()):
            raise ValueError(f"Неверный диапазон портов: {spec}")
        ends = [int(x) for x in piece.split("-")]
        lo, hi = ends[0], ends[-1]
        if not minimum <= lo <= hi <= 65535:
            raise ValueError(f"Порты должны быть в пределах {minimum}–65535")
        result.append((lo, hi))
    return result


def union_ports(specs: Iterable[str]) -> str:
    intervals = sorted(pair for spec in specs if spec for pair in port_intervals(spec))
    merged: list[list[int]] = []
    for lo, hi in intervals:
        if merged and lo <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return ",".join(str(lo) if lo == hi else f"{lo}-{hi}" for lo, hi in merged)


@dataclass(frozen=True)
class Block:
    id: str
    category: str
    args: tuple[str, ...]
    source: str = "custom"
    label: str = ""
    scope: str = "loaded"

    @classmethod
    def from_dict(cls, data):
        return cls(**{**data, "args": tuple(data["args"])})

    def to_dict(self):
        return asdict(self)

    @property
    def complexity(self) -> int:
        repeats = next((a.split("=", 1)[1] for a in self.args
                        if a.startswith("--dpi-desync-repeats=")), "1")
        return int(repeats) + len(self.args)


@dataclass
class Strategy:
    id: str
    name: str
    blocks: list[Block]
    global_args: list[str] = field(default_factory=list)
    source: str = "custom"
    original_argv: list[str] = field(default_factory=list)

    def to_dict(self):
        return {**asdict(self), "blocks": [b.to_dict() for b in self.blocks]}

    @classmethod
    def from_dict(cls, data):
        return cls(**{**data, "blocks": [Block.from_dict(b) for b in data["blocks"]]})

    def reassemble(self) -> list[str]:
        argv = list(self.global_args)
        for index, block in enumerate(self.blocks):
            if index:
                argv.append("--new")
            argv.extend(block.args)
        return argv


def compose(blocks: Iterable[Block], game_mode="all", ipset_mode="loaded", *,
            variables: dict[str, str], services: Iterable[str] = ("youtube", "discord", "fortnite"),
            tcp_ports="1024-65535", udp_ports="1024-65535") -> list[str]:
    if game_mode not in {"none", "tcp", "udp", "all"} or ipset_mode not in {"none", "loaded", "any"}:
        raise ValueError("Неизвестный режим Game Filter или IPSet")
    port_intervals(tcp_ports, 1024)
    port_intervals(udp_ports, 1024)
    service_set = set(services)
    if not service_set <= SERVICE_CATEGORIES.keys():
        raise ValueError("Неизвестный сервис")
    enabled = set().union(*(SERVICE_CATEGORIES[s] for s in service_set))
    values = {**variables, "GAME_TCP": tcp_ports, "GAME_UDP": udp_ports}
    selected: list[Block] = []
    seen: dict[str, str] = {}
    for block in sorted(blocks, key=lambda b: ORDER.index(b.category)):
        if block.category not in enabled or (block.category in seen and seen[block.category] != block.source):
            continue
        game = block.category.startswith("game-")
        if (game and (game_mode == "none" or (game_mode != "all" and
                     block.category != f"game-{game_mode}"))) or (
                     ipset_mode == "none" and block.category.startswith(("ipset-", "game-"))):
            continue
        args = list(block.args)
        if block.category == "yt-quic" and not any(a.startswith("--filter-udp=") for a in args):
            args.insert(0, "--filter-udp=443")
        if game:
            args = [a for a in args if not a.startswith("--ipset=")]
            if ipset_mode == "loaded":
                args += ["--ipset=${LISTS}/ipset-game.txt"]
        args = [resolve(a, values) for a in args]
        for protocol in ("tcp", "udp"):
            if game:
                for arg in args:
                    if arg.startswith(f"--filter-{protocol}="):
                        port_intervals(arg.split("=", 1)[1], 1024)
        seen[block.category] = block.source
        selected.append(replace(block, args=tuple(args)))
    if not selected:
        raise ValueError("Включите хотя бы один сервис с доступными блоками")
    argv = []
    for proto in ("tcp", "udp"):
        ports = union_ports(a.split("=", 1)[1] for b in selected for a in b.args
                            if a.startswith(f"--filter-{proto}="))
        if ports:
            argv.append(f"--wf-{proto}={ports}")
    for i, block in enumerate(selected):
        if i:
            argv.append("--new")
        argv.extend(block.args)
    return argv
