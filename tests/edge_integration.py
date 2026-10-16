"""Regression for trim plus size splitting, subtitles and selected audio."""
from dataclasses import asdict
import json
from pathlib import Path
import sys

from zhendu.config import JobConfig, atomic_json
from zhendu.engine import Engine
from zhendu.media import probe
from zhendu.paths import media_binary
from zhendu.process import Runner

root = Path(sys.argv[1]).resolve()
source = Path(sys.argv[2]).resolve()
root.mkdir(parents=True, exist_ok=True)
runner = Runner()
srt = root / "caption.srt"
srt.write_text("1\n00:00:00,000 --> 00:00:04,000\nZhenDu subtitle test\n", encoding="utf-8")
multi = root / "two-audio-subtitle.mkv"
runner.capture([media_binary("ffmpeg.exe"), "-v", "error", "-y", "-i", str(source), "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000",
                "-i", str(srt), "-t", "18", "-map", "0:v:0", "-map", "0:a:0", "-map", "1:a:0", "-map", "2:s:0",
                "-c:v", "copy", "-c:a", "aac", "-c:s", "srt", str(multi)])
report = {"cases": []}
configs = [
    ("clip_size_copy", source, JobConfig(clip=True, clip_start=3, clip_end=13, split=True, split_mode="size", split_size_mb=1, size_safe=False)),
    ("selected_audio_drop_subtitle_mp4", multi, JobConfig(container="mp4", audio_track=1, clip=True, clip_start=3, clip_end=13, split=True, split_mode="size", split_size_mb=1, size_safe=False)),
    ("copy_subtitle_mkv", multi, JobConfig(audio_track=1, subtitles=True, clip=True, clip_start=3, clip_end=13, split=True, split_mode="size", split_size_mb=1, size_safe=False)),
]
def hashes(path):
    data = runner.capture([media_binary("ffprobe.exe"), "-v", "error", "-select_streams", "v:0", "-show_packets", "-show_data_hash", "sha256", "-show_entries", "packet=data_hash", "-of", "json", str(path)])
    return {packet["data_hash"] for packet in json.loads(data)["packets"]}
original_packets = hashes(source)
for name, path, config in configs:
    result = Engine().process(path, config, root / "outputs")
    for output in result.outputs:
        info = probe(output)
        assert hashes(output) <= original_packets, "Video was re-encoded"
        if config.audio_track >= 0:
            assert len(info.audio) == 1
        stream_data = json.loads(runner.capture([media_binary("ffprobe.exe"), "-v", "error", "-show_streams", "-of", "json", output]))
        assert any(stream.get("codec_type") == "subtitle" for stream in stream_data["streams"]) == config.subtitles
        runner.capture([media_binary("ffmpeg.exe"), "-v", "error", "-i", output, "-f", "null", "-"], timeout=30)
    report["cases"].append({"name": name, "ok": True, "outputs": len(result.outputs), "config": asdict(config)})
report["ok"] = True
atomic_json(root / "edge-report.json", report)
print("Trim-size, selected audio and subtitles passed without video re-encoding.")
