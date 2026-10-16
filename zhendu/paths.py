import os
from pathlib import Path
import sys


def app_root():
    return Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent


def resource_path(name):
    bundle = Path(getattr(sys, "_MEIPASS", app_root()))
    return bundle / name


def config_root():
    override = os.environ.get("ZHENDU_CONFIG_DIR")
    if override:
        return Path(override).resolve()
    portable = app_root() / "portable.flag"
    if portable.exists():
        return app_root() / "user_data"
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".config"))) / "ZhenDu"


def media_binary(name):
    override = os.environ.get("ZHENDU_FFMPEG_DIR")
    candidates = [Path(override) / name] if override else []
    candidates += [app_root() / "ffmpeg" / "bin" / name, resource_path("ffmpeg/bin") / name]
    for path in candidates:
        if path.is_file():
            return str(path.resolve())
    raise FileNotFoundError(f"Missing {name}: {app_root() / 'ffmpeg' / 'bin'}")
