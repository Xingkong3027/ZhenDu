"""Fetch the exact upstream tools used by the first public release."""
import hashlib
from pathlib import Path
import shutil
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent
VERSION = "2026-01-29-git-c898ddb8fe"
URL = ("https://github.com/GyanD/codexffmpeg/releases/download/" + VERSION
       + "/ffmpeg-" + VERSION + "-full_build.zip")
ARCHIVE_SHA256 = "e90a9fc37bcc8cc66fe45f59c9eb05ce364f08eb48624c8aba60a6f57666811c"
BINARIES = {
    "ffmpeg.exe": "79bdd4c65adc74d4ca937b6a9d939349806d6c66c8a42c848b0e866bcbdf4eb7",
    "ffprobe.exe": "befa1cc68809369b1f40c84387285bc5ebe1013974cdd69528242ffe49e55830",
}


def digest(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    destination = ROOT / "ffmpeg"
    if all((destination / "bin" / name).is_file() and digest(destination / "bin" / name) == expected
           for name, expected in BINARIES.items()) and all((destination / name).is_file() for name in ("LICENSE", "README.txt")):
        print("Pinned FFmpeg and ffprobe already available.")
        return
    with tempfile.TemporaryDirectory(prefix="zhendu-ffmpeg-") as directory:
        archive_path = Path(directory) / "ffmpeg.zip"
        print("Downloading:", URL, flush=True)
        request = urllib.request.Request(URL, headers={"User-Agent": "ZhenDu-source-builder"})
        with urllib.request.urlopen(request, timeout=120) as response, archive_path.open("wb") as output:
            shutil.copyfileobj(response, output)
        if digest(archive_path) != ARCHIVE_SHA256:
            raise ValueError("FFmpeg download SHA256 mismatch; nothing installed")
        with zipfile.ZipFile(archive_path) as archive:
            staged = {}
            for name in (*BINARIES, "LICENSE", "README.txt"):
                suffix = "/bin/" + name if name.endswith(".exe") else "/" + name
                matches = [item for item in archive.infolist() if not item.is_dir() and item.filename.endswith(suffix)]
                if len(matches) != 1:
                    raise ValueError("Missing or ambiguous archive entry: " + name)
                path = Path(directory) / name
                with archive.open(matches[0]) as source, path.open("wb") as output:
                    shutil.copyfileobj(source, output)
                if name in BINARIES and digest(path) != BINARIES[name]:
                    raise ValueError("FFmpeg executable SHA256 mismatch: " + name)
                staged[name] = path
        (destination / "bin").mkdir(parents=True, exist_ok=True)
        for name, path in staged.items():
            shutil.copy2(path, destination / "bin" / name if name.endswith(".exe") else destination / name)
    print("Verified FFmpeg and ffprobe installed in ffmpeg/bin.")


if __name__ == "__main__":
    main()
