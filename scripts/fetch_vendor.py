"""Download the immutable upstream ZIP, verify it before extracting, import BAT data."""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
VERSION = "1.10.3"
URL = f"https://github.com/Flowseal/zapret-discord-youtube/releases/download/{VERSION}/zapret-discord-youtube-{VERSION}.zip"
# GitHub release asset digest; independently checked before the first import.
SHA256 = "244314ae1c24538a0d751601da8e0c925c843371eec4456eb15f14c4fd6b7058"


def extract_verified(data: bytes, destination: Path):
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise ValueError("SHA256 архива Flowseal не совпал. Файлы не извлечены.")
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    if any(destination.iterdir()):
        raise ValueError("Распаковывать можно только в пустой каталог")
    import io
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for info in archive.infolist():
            path = PurePosixPath(info.filename.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or ":" in str(path) or info.file_size > 32_000_000:
                raise ValueError("Небезопасный путь или размер в ZIP")
            if info.external_attr >> 16 & 0o170000 == 0o120000:
                raise ValueError("Символические ссылки в ZIP запрещены")
        if sum(i.file_size for i in archive.infolist()) > 64_000_000:
            raise ValueError("Архив слишком большой")
        archive.extractall(destination)


def main():
    from obhod.core.importer import import_directory
    cached = ROOT / "vendor" / f"flowseal-{VERSION}.zip"
    if cached.exists():
        data = cached.read_bytes()
    else:
        request = urllib.request.Request(URL, headers={"User-Agent": "Obhod/0.1"})
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(16_000_001)
        if len(data) > 16_000_000:
            raise ValueError("Неожиданный размер архива")
    with tempfile.TemporaryDirectory(prefix="obhod-flowseal-") as folder:
        extract_verified(data, Path(folder))
        source = Path(folder) / f"zapret-discord-youtube-{VERSION}"
        strategies = import_directory(source, ROOT / "strategies" / "flowseal")
        for name in ("bin", "lists"):
            shutil.copytree(source / name, ROOT / name, dirs_exist_ok=True)
        # Keep source BATs and test target provenance alongside the pinned archive.
        vendor = ROOT / "vendor" / f"flowseal-{VERSION}"
        vendor.mkdir(parents=True, exist_ok=True)
        for bat in source.glob("general*.bat"):
            shutil.copy2(bat, vendor / bat.name)
        shutil.copy2(source / "utils" / "targets.txt", vendor / "targets.txt")
    cached.parent.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(data)
    (ROOT / "bin" / "zero.bin").write_bytes(bytes(32))
    (ROOT / "vendor" / "manifest.json").write_text(json.dumps(
        {"version": VERSION, "url": URL, "sha256": SHA256, "strategy_count": len(strategies)}, indent=2))
    print(f"Flowseal {VERSION}: SHA256 OK, {len(strategies)} стратегий импортировано без потерь")


if __name__ == "__main__":
    main()
