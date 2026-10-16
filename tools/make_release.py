"""Archive an exact Git source commit and the tested Windows distribution."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent.parent


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args]).decode("utf-8").strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="release-assets")
    args = parser.parse_args()
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    version = re.search(r'__version__ = "([^"]+)"', (ROOT / "zhendu" / "__init__.py").read_text()).group(1)
    commit = git("rev-parse", "HEAD")
    release = ROOT / "dist" / "ZhenDu"
    for name in ("ZhenDu.exe", "README.md", "README.en.md", "LICENSE", "ffmpeg/bin/ffmpeg.exe", "ffmpeg/bin/ffprobe.exe"):
        if not (release / name).is_file():
            raise FileNotFoundError(name)
    portable = output / f"ZhenDu-{version}-windows-x64-portable.zip"
    with zipfile.ZipFile(portable, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(release.rglob("*")):
            if path.is_file():
                archive.write(path, Path("ZhenDu") / path.relative_to(release))
    with zipfile.ZipFile(portable) as archive:
        if archive.testzip() is not None:
            raise ValueError("Portable ZIP CRC failed")
        if any(name.endswith("ffplay.exe") for name in archive.namelist()):
            raise ValueError("Unused ffplay was bundled")
    source = output / f"ZhenDu-{version}-source.zip"
    subprocess.run(["git", "-C", str(ROOT), "archive", "--format=zip", f"--prefix=ZhenDu-{version}/", "--output", str(source), commit], check=True)
    files = git("ls-tree", "-r", "--name-only", commit).splitlines()
    with zipfile.ZipFile(source) as archive:
        prefix = f"ZhenDu-{version}/"
        archived = {name[len(prefix):] for name in archive.namelist() if not name.endswith("/")}
        if archived != set(files):
            raise ValueError("Source archive file set differs from Git")
        for name in files:
            expected = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{commit}:{name}"])
            if archive.read(prefix + name) != expected:
                raise ValueError("Source bytes differ: " + name)
    info = {
        "version": version, "tag": "v" + version, "source_commit": commit,
        "toolchain": {name: importlib.metadata.version(name) for name in ("PySide6", "PyInstaller")},
        "python": __import__("sys").version.split()[0],
        "files": {name: digest(release / name) for name in ("ZhenDu.exe", "ffmpeg/bin/ffmpeg.exe", "ffmpeg/bin/ffprobe.exe")},
        "source_archive_verified_against_git": True,
        "languages": ["zh_CN", "en"], "ffmpeg_recompiled": False,
    }
    (output / "BUILD_INFO.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    sums = "".join(f"{digest(path)}  {path.name}\n" for path in sorted(output.iterdir()) if path.is_file())
    (output / "SHA256SUMS.txt").write_text(sums, encoding="utf-8")
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
