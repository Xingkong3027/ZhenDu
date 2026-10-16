from dataclasses import dataclass, field
from fractions import Fraction
import json
from pathlib import Path
import threading

from .config import parse_time
from .language import UserError
from .paths import media_binary
from .process import Runner


@dataclass
class MediaInfo:
    path: str
    duration: float
    size: int
    width: int
    height: int
    fps: float
    video_index: int
    video_codec: str
    start_time: float = 0.0
    video_duration: float = 0.0
    audio: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)


def number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def probe(path, runner=None):
    runner = runner or Runner()
    data = json.loads(runner.capture([media_binary("ffprobe.exe"), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)]))
    streams = data.get("streams", [])
    videos = [stream for stream in streams if stream.get("codec_type") == "video" and not stream.get("disposition", {}).get("attached_pic")]
    if not videos:
        raise UserError("没有检测到可处理的视频流。", "No usable video stream was found.")
    video = videos[0]
    fmt = data.get("format", {})
    duration = number(fmt.get("duration"))
    video_duration = number(video.get("duration"))
    if not video_duration:
        try:
            video_duration = parse_time(video.get("tags", {}).get("DURATION", ""))
        except ValueError:
            pass
    duration = duration or video_duration
    if duration <= 0:
        raise UserError("无法读取视频时长。", "Unable to read video duration.")
    try:
        fps = float(Fraction(video.get("avg_frame_rate", "0/1")))
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    return MediaInfo(str(Path(path).resolve()), duration, int(number(fmt.get("size"), Path(path).stat().st_size)),
                     video.get("width", 0), video.get("height", 0), fps, video["index"], video.get("codec_name", ""),
                     number(fmt.get("start_time")), video_duration,
                     [stream for stream in streams if stream.get("codec_type") == "audio"], data)


class ProbeCache:
    def __init__(self):
        self.values = {}
        self.lock = threading.Lock()

    def get(self, path, runner=None):
        path = Path(path).resolve()
        stat = path.stat()
        key = (str(path).casefold(), stat.st_size, stat.st_mtime_ns)
        with self.lock:
            existing = self.values.get(key)
        if existing:
            return existing
        info = probe(path, runner)
        with self.lock:
            self.values[key] = info
        return info


def video_span(path, runner):
    args = [media_binary("ffprobe.exe"), "-v", "error", "-select_streams", "v:0", "-show_packets",
            "-show_entries", "packet=pts_time,duration_time", "-of", "compact=p=0:nk=0", str(path)]
    first, end = None, 0.0
    previous, step = None, 0.0
    for line in runner.lines(args):
        values = dict(item.split("=", 1) for item in line.split("|") if "=" in item)
        pts = number(values.get("pts_time"), None)
        if pts is None:
            continue
        first = pts if first is None else min(first, pts)
        packet_duration = number(values.get("duration_time"))
        if previous is not None and pts > previous:
            step = pts - previous
        previous = pts
        end = max(end, pts + packet_duration)
    if first is None:
        raise UserError("分段没有有效的视频数据。", "The segment has no valid video data.")
    if end <= first:
        end += step
    return first, max(0.0, end - first)
