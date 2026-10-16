"""Verify downloaded release assets without requiring GUI dependencies."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    root = args.directory
    lines = (root / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    names = set()
    for line in lines:
        expected, name = line.split("  ", 1)
        if Path(name).name != name or name in names:
            raise ValueError("Invalid asset name")
        names.add(name)
        with (root / name).open("rb") as handle:
            if hashlib.file_digest(handle, "sha256").hexdigest() != expected:
                raise ValueError("SHA256 mismatch: " + name)
    actual = {path.name for path in root.iterdir() if path.is_file()}
    if actual != names | {"SHA256SUMS.txt"}:
        raise ValueError("Missing or extra assets")
    info = json.loads((root / "BUILD_INFO.json").read_text())
    if info["version"] != args.version or info["source_commit"] != args.commit:
        raise ValueError("Version/source commit mismatch")
    source = root / f"ZhenDu-{args.version}-source.zip"
    prefix = f"ZhenDu-{args.version}/"
    with zipfile.ZipFile(source) as archive:
        if archive.testzip() is not None:
            raise ValueError("Source archive CRC failed")
        for name in ("README.md", "README.en.md", "LICENSE", "RELEASE_NOTES.md", "zhendu/player.py", "zhendu/engine.py"):
            if not archive.read(prefix + name):
                raise ValueError("Source file missing or empty: " + name)
    with zipfile.ZipFile(root / f"ZhenDu-{args.version}-windows-x64-portable.zip") as archive:
        if archive.testzip() is not None:
            raise ValueError("Portable archive CRC failed")
        for name in ("README.md", "README.en.md", "LICENSE", "docs/THIRD_PARTY_SOURCES.md"):
            if not archive.read("ZhenDu/" + name):
                raise ValueError("Portable documentation missing: " + name)
        for name, expected in info["files"].items():
            if hashlib.sha256(archive.read("ZhenDu/" + name)).hexdigest() != expected:
                raise ValueError("Bundled binary mismatch: " + name)
    print("Release assets, binaries, bilingual documentation and source metadata verified.")


if __name__ == "__main__":
    main()
