from dataclasses import asdict, dataclass, fields
import json
import math
import os
from pathlib import Path
import re
import tempfile
import uuid

from .language import UserError, t
from .paths import config_root


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as handle:
            temporary = Path(handle.name)
            json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def parse_time(value):
    parts = str(value).strip().split(":")
    if not 1 <= len(parts) <= 3:
        raise ValueError("Invalid time")
    numbers = [float(part) for part in parts]
    if any(number < 0 or number != number or number == float("inf") for number in numbers):
        raise ValueError("Invalid time")
    if len(numbers) > 1 and numbers[-1] >= 60:
        raise ValueError("Seconds must be below 60")
    if len(numbers) == 3 and numbers[1] >= 60:
        raise ValueError("Minutes must be below 60")
    total = 0.0
    for number in numbers:
        total = total * 60 + number
    return total


def time_text(seconds):
    milliseconds = max(0, round(float(seconds) * 1000))
    hours, rest = divmod(milliseconds, 3600000)
    minutes, rest = divmod(rest, 60000)
    seconds, ms = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"


def safe_name(name):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(name)).strip(" .")[:100]
    if re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)", value, re.I):
        value = "_" + value
    return value or "video"


@dataclass
class JobConfig:
    compress: bool = False
    codec: str = "h264"
    backend: str = "cpu"
    speed: str = "medium"
    quality: int = 20
    width: int = 0
    height: int = 0
    fps: float = 0.0
    color_range: str = "source"
    audio_mode: str = "copy"
    audio_bitrate: int = 128
    audio_track: int = -1
    container: str = "auto"
    subtitles: bool = False
    clip: bool = False
    clip_start: float = 0.0
    clip_end: float | None = None
    split: bool = False
    split_mode: str = "count"
    split_count: int = 2
    split_duration: float = 300.0
    split_size_mb: float = 100.0
    size_safe: bool = True

    @classmethod
    def from_dict(cls, value):
        allowed = {field.name for field in fields(cls)}
        result = cls(**{key: item for key, item in value.items() if key in allowed})
        result.validate()
        return result

    def validate(self):
        for key in ("quality", "width", "height", "audio_bitrate", "audio_track", "split_count"):
            if type(getattr(self, key)) is not int:
                raise UserError("无效数值：{key}", "Invalid number: {key}", key=key)
        for key in ("fps", "clip_start", "split_duration", "split_size_mb"):
            value = getattr(self, key)
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise UserError("无效数值：{key}", "Invalid number: {key}", key=key)
        if self.clip_end is not None and (not isinstance(self.clip_end, (int, float)) or not math.isfinite(self.clip_end)):
            raise UserError("无效终点时间。", "Invalid end time.")
        if self.audio_track < -1:
            raise UserError("无效音轨。", "Invalid audio track.")
        choices = {"codec": {"h264", "hevc", "vp9", "av1"}, "backend": {"cpu", "nvenc", "qsv", "amf"},
                   "speed": {"ultrafast", "veryfast", "fast", "medium", "slow", "veryslow"},
                   "audio_mode": {"copy", "encode", "none"}, "container": {"auto", "mp4", "mkv", "webm", "mov", "ts"},
                   "color_range": {"source", "limited", "full"}, "split_mode": {"count", "duration", "size"}}
        for key, allowed in choices.items():
            if getattr(self, key) not in allowed:
                raise UserError("无效设置：{key}", "Invalid setting: {key}", key=key)
        if not isinstance(self.quality, int) or not 0 <= self.quality <= 63:
            raise UserError("质量值必须为 0～63。", "Quality must be between 0 and 63.")
        if not 0 <= self.width <= 16384 or not 0 <= self.height <= 16384 or not 0 <= self.fps <= 240:
            raise UserError("分辨率或帧率超出范围。", "Resolution or frame rate is out of range.")
        if any(value and value % 2 for value in (self.width, self.height)):
            raise UserError("目标宽高需为偶数；0 表示自动。", "Target dimensions must be even; 0 means automatic.")
        if self.clip and (self.clip_start < 0 or self.clip_end is not None and self.clip_end <= self.clip_start):
            raise UserError("终点 B 必须大于起点 A。", "End B must be after start A.")
        if self.split and (not 2 <= self.split_count <= 1000 or self.split_duration <= 0 or self.split_size_mb < 1):
            raise UserError("分段数需为 2～1000，时长需大于 0，大小至少 1 MiB。", "Use 2–1000 parts, a positive duration, and at least 1 MiB.")
        if not 8 <= self.audio_bitrate <= 1536:
            raise UserError("音频码率超出范围。", "Audio bitrate is out of range.")
        # Copy mode never secretly enables video encoding from stale controls.
        if not self.compress:
            self.width = self.height = 0
            self.fps = 0.0
            self.color_range = "source"

    def bounds(self, duration):
        start = self.clip_start if self.clip else 0.0
        end = min(self.clip_end if self.clip and self.clip_end is not None else duration, duration)
        if duration <= 0 or start >= end:
            raise UserError("截取范围超出该视频时长。", "The trim range is outside this video's duration.")
        return start, end


PRESET_FIELDS = {"compress", "codec", "backend", "speed", "quality", "width", "height", "fps", "color_range",
                 "audio_mode", "audio_bitrate", "audio_track", "container", "subtitles"}
TASK_FIELDS = {"split", "split_mode", "split_count", "split_duration", "split_size_mb", "size_safe"}


class Store:
    VERSION = 1

    def __init__(self, root=None):
        self.root = Path(root) if root else config_root()
        self.path = self.root / "settings.json"
        self.load_warning = ""
        self.data = {"schema_version": self.VERSION, "language": "auto", "output_dir": "", "presets": [], "last_config": {}}
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if not isinstance(loaded, dict):
                    raise ValueError("Invalid settings")
                if loaded.get("schema_version", 1) > self.VERSION:
                    raise UserError("设置由更新版本创建，请使用更新版本打开。原文件未修改。", "Settings were created by a newer version. Open them with that version; the file was not modified.")
                if not isinstance(loaded.get("presets", []), list):
                    raise ValueError("Invalid preset list")
                for preset in loaded.get("presets", []):
                    self.validate_preset(preset)
                self.data.update(loaded)
            except (ValueError, TypeError, KeyError) as error:
                backup = self.path.with_name("settings.recovery-" + uuid.uuid4().hex[:8] + ".json")
                backup.write_bytes(self.path.read_bytes())
                self.load_warning = str(error)
        if not self.data["presets"]:
            self.data["presets"] = [
                {"id": "builtin-everyday", "name": "", "name_zh": "日常压缩 · H.264", "name_en": "Everyday · H.264", "context": True,
                 "settings": {"compress": True, "codec": "h264", "speed": "fast", "quality": 22, "audio_mode": "encode"}},
                {"id": "builtin-archive", "name": "", "name_zh": "高清保留 · H.265", "name_en": "Archive · H.265", "context": True,
                 "settings": {"compress": True, "codec": "hevc", "speed": "medium", "quality": 22, "audio_mode": "copy"}},
                {"id": "builtin-split", "name": "", "name_zh": "100 MiB 快速分割", "name_en": "100 MiB fast split", "context": True,
                 "settings": {"compress": False, "split": True, "split_mode": "size", "split_size_mb": 100.0, "size_safe": False}}]
        if self.data.get("language") not in {"auto", "zh_CN", "en"}:
            self.data["language"] = "auto"

    @staticmethod
    def validate_preset(preset):
        if not isinstance(preset, dict) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", preset["id"]):
            raise ValueError("Invalid preset identifier")
        JobConfig.from_dict(preset["settings"])
        if not isinstance(preset.get("name", ""), str):
            raise ValueError("Invalid preset name")

    @staticmethod
    def preset_name(preset):
        return preset.get("name") or t(preset.get("name_zh", "预设"), preset.get("name_en", "Preset"))

    @property
    def presets(self):
        return self.data["presets"]

    def save(self):
        atomic_json(self.path, self.data)

    def get_preset(self, identifier):
        return next((preset for preset in self.presets if preset["id"] == identifier), None)

    def save_preset(self, name, config, context=True, include_task=False, include_clip=False, identifier=None):
        if not name.strip():
            raise UserError("请输入预设名称。", "Enter a preset name.")
        config.validate()
        keep = PRESET_FIELDS | (TASK_FIELDS if include_task else set()) | ({"clip", "clip_start", "clip_end"} if include_clip else set())
        preset = {"id": identifier or uuid.uuid4().hex, "name": name.strip()[:80], "context": bool(context),
                  "settings": {key: value for key, value in asdict(config).items() if key in keep}}
        self.validate_preset(preset)
        self.data["presets"] = [item for item in self.presets if item["id"] != preset["id"]] + [preset]
        self.save()
        return preset
