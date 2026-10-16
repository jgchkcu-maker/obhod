"""Read commands as data. Never invoke a downloaded .bat file."""
from __future__ import annotations

import re
from pathlib import Path

from .paths import atomic_json
from .strategy import Block, Strategy


def tokenize(command: str) -> list[str]:
    # Batch arguments use quotes inside --key="path with spaces". shlex would
    # eat Windows backslashes; these scripts do not use escaped quote literals.
    tokens, current, quoted = [], [], False
    for char in command:
        if char == '"':
            quoted = not quoted
        elif char.isspace() and not quoted:
            if current:
                tokens.append("".join(current))
                current = []
        else:
            current.append(char)
    if quoted:
        raise ValueError("Незакрытая кавычка в winws-команде")
    if current:
        tokens.append("".join(current))
    return tokens


def extract_command(text: str) -> list[str]:
    joined = re.sub(r"\^\s*\r?\n", " ", text.lstrip("\ufeff"))
    line = next((x for x in joined.splitlines() if re.search(r"winws\.exe\"?\s+--", x, re.I)), None)
    if line is None:
        raise ValueError("Команда winws.exe не найдена")
    command = re.split(r"winws\.exe\"?\s+", line, maxsplit=1, flags=re.I)[1]
    return tokenize(command)


def canonical(arg: str) -> str:
    replacements = {"%BIN%": "${BIN}/", "%LISTS%": "${LISTS}/",
                    "%GameFilterTCP%": "${GAME_TCP}", "%GameFilterUDP%": "${GAME_UDP}"}
    for old, new in replacements.items():
        arg = re.sub(re.escape(old), lambda _: new, arg, flags=re.I)
    if "%" in arg:
        raise ValueError(f"Неподдерживаемая batch-переменная: {arg}")
    return arg.replace("\\", "/")


def classify(args: list[str]) -> str:
    text = " ".join(args).lower()
    if "${game_tcp}" in text:
        return "game-tcp"
    if "${game_udp}" in text:
        return "game-udp"
    if "--filter-udp=19294" in text or "--filter-l7=discord" in text:
        return "discord-voice"
    if "discord.media" in text:
        return "discord-media"
    if "list-google" in text:
        return "google-tcp"
    if "--ipset=" in text:
        return "ipset-udp" if "--filter-udp=" in text else "ipset-tcp"
    if ("--filter-udp=443" in text or "--filter-l7=quic" in text) and "--hostlist=" in text:
        return "yt-quic"
    if "--filter-tcp=" in text:
        return "general-tcp"
    raise ValueError(f"Не удалось классифицировать блок: {text}")


def parse_bat(path: Path) -> Strategy:
    original = [canonical(a) for a in extract_command(path.read_text(encoding="utf-8-sig"))]
    identifier = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
    global_args, chunks = [], [[]]
    for arg in original:
        if arg == "--new":
            chunks.append([])
        elif arg.startswith("--wf-"):
            if any(chunks):
                raise ValueError("Глобальный фильтр оказался внутри профиля")
            global_args.append(arg)
        else:
            chunks[-1].append(arg)
    if not all(chunks):
        raise ValueError("Пустой профиль winws")
    blocks = [Block(f"{identifier}:{i}", classify(chunk), tuple(chunk), identifier)
              for i, chunk in enumerate(chunks)]
    strategy = Strategy(identifier, path.stem, blocks, global_args, "Flowseal 1.10.3", original)
    if strategy.reassemble() != original:
        raise ValueError("Команда потеряла аргументы при импорте")
    return strategy


def import_directory(source: Path, target: Path) -> list[Strategy]:
    parsed = [parse_bat(p) for p in sorted(source.glob("general*.bat"))]
    if not parsed:
        raise ValueError("В архиве отсутствуют general*.bat")
    target.mkdir(parents=True, exist_ok=True)
    for strategy in parsed:
        atomic_json(target / f"{strategy.id}.json", strategy.to_dict())
    return parsed
