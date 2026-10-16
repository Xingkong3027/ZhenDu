"""Reproducible onedir Windows build. FFmpeg stays beside the executable."""
from pathlib import Path
import os
import shutil
import subprocess
import sys

import PySide6

root = Path(__file__).resolve().parent.parent
subprocess.run([sys.executable, "-B", str(root / "tools" / "make_icon.py")], cwd=root, check=True)
qt = Path(PySide6.__file__).parent
translation = qt / "translations" / "qtbase_zh_CN.qm"
shutil.copy2(translation, root / "assets" / translation.name)
command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed", "--onedir", "--noupx",
           "--name", "ZhenDu", "--icon", str(root / "assets" / "zhendu.ico"), "--add-data", str(root / "assets") + ";assets",
           "--distpath", str(root / "dist"), "--workpath", str(root / "build" / "cache"), "--specpath", str(root / "build")]
for module in ("tkinter", "customtkinter", "PySide2", "PyQt5", "PyQt6", "PySide6.QtQml", "PySide6.QtQuick",
               "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtNetworkAuth"):
    command += ["--exclude-module", module]
for pattern in ("avcodec-*.dll", "avformat-*.dll", "avutil-*.dll", "swscale-*.dll", "swresample-*.dll"):
    for binary in qt.glob(pattern):
        command += ["--add-binary", str(binary) + ";PySide6"]
command.append(str(root / "video_tool_clip_player.py"))
if "--reuse" in sys.argv:
    command.remove("--clean")
# Prevent unrelated tools on PATH from supplying incompatible Qt dependencies.
build_environment = dict(os.environ)
build_environment["PYTHONHASHSEED"] = "0"
windows = Path(os.environ.get("SYSTEMROOT", "C:/Windows"))
build_environment["PATH"] = os.pathsep.join(str(path) for path in (
    Path(sys.prefix) / "Scripts", Path(sys.base_prefix), qt, qt.parent / "shiboken6", windows / "System32", windows))
subprocess.run(command, cwd=root, env=build_environment, check=True)
release = root / "dist" / "ZhenDu"
(release / "ffmpeg" / "bin").mkdir(parents=True, exist_ok=True)
for filename in ("ffmpeg.exe", "ffprobe.exe"):
    source = root / "ffmpeg" / "bin" / filename
    if not source.is_file():
        raise FileNotFoundError(source)
    shutil.copy2(source, release / "ffmpeg" / "bin" / filename)
for filename in ("LICENSE", "README.txt"):
    shutil.copy2(root / "ffmpeg" / filename, release / "ffmpeg" / filename)
for filename in ("README.md", "README.en.md", "LICENSE", "CHANGELOG.md", "RELEASE_NOTES.md", "CONTRIBUTING.md", "THIRD_PARTY_NOTICES.md"):
    shutil.copy2(root / filename, release / filename)
shutil.copytree(root / "docs", release / "docs", dirs_exist_ok=True)
(release / "assets").mkdir(exist_ok=True)
shutil.copy2(root / "assets" / "zhendu.png", release / "assets" / "zhendu.png")
license_root = release / "licenses"
license_root.mkdir(exist_ok=True)
for directory in qt.parent.glob("*.dist-info"):
    if directory.name.startswith(("pyside6", "shiboken6", "pyinstaller")) and (directory / "licenses").is_dir():
        shutil.copytree(directory / "licenses", license_root / directory.name, dirs_exist_ok=True)
python_license = Path(sys.base_prefix) / "LICENSE.txt"
if python_license.exists():
    shutil.copy2(python_license, license_root / "Python-LICENSE.txt")
print("Build complete:", release / "ZhenDu.exe")
