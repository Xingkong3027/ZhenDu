"""Actual FFmpeg regression checks; artifacts live in the provided scratch directory."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
import time

from zhendu.config import JobConfig, atomic_json
from zhendu.engine import Engine
from zhendu.media import probe
from zhendu.paths import media_binary
from zhendu.process import Cancelled, Runner

root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=True)
runner = Runner()
media = root / "media"
media.mkdir(exist_ok=True)
source = media / "测试 视频 18秒.mp4"
short = media / "短片 4秒.mp4"
silent = media / "silent.mp4"
if not source.exists():
    runner.capture([media_binary("ffmpeg.exe"), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=30",
                    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "18", "-c:v", "libx264", "-preset", "ultrafast",
                    "-crf", "18", "-g", "30", "-sc_threshold", "0", "-c:a", "aac", "-b:a", "128k", str(source)], timeout=90)
if not short.exists():
    runner.capture([media_binary("ffmpeg.exe"), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=180x320:rate=24",
                    "-f", "lavfi", "-i", "sine=frequency=880:sample_rate=48000", "-t", "4", "-c:v", "libx264", "-preset", "ultrafast",
                    "-g", "24", "-c:a", "aac", str(short)], timeout=30)
if not silent.exists():
    runner.capture([media_binary("ffmpeg.exe"), "-v", "error", "-y", "-i", str(short), "-an", "-c:v", "copy", str(silent)])


def packets(path):
    data = runner.capture([media_binary("ffprobe.exe"), "-v", "error", "-select_streams", "v:0", "-show_packets", "-show_data_hash", "sha256",
                           "-show_entries", "packet=data_hash", "-of", "json", str(path)])
    return [packet["data_hash"] for packet in json.loads(data)["packets"]]


report = {"source": str(source), "short": str(short), "cases": []}
source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
source_packets = packets(source)


def check(name, config, source_path=source, assertion=None):
    began = time.monotonic()
    engine = Engine()
    result = engine.process(source_path, config, root / "outputs", task_subfolders=True)
    infos = [probe(path) for path in result.outputs]
    if assertion:
        assertion(result, infos)
    if not config.compress:
        assert all(info.video_codec == "h264" for info in infos), name
        for path in result.outputs:
            # Exact encoded packet hashes prove stream copy rather than transcoding.
            assert set(packets(path)) <= set(source_packets if source_path == source else packets(source_path)), name
    for path in result.outputs:
        runner.capture([media_binary("ffmpeg.exe"), "-v", "error", "-i", path, "-f", "null", "-"], timeout=60)
    manifest = json.loads((Path(result.directory) / "task.json").read_text(encoding="utf-8"))
    entry = {"name": name, "ok": True, "count": len(infos), "durations": [round(info.duration, 3) for info in infos],
             "sizes": [info.size for info in infos], "seconds": round(time.monotonic() - began, 2), "config": asdict(config),
             "all_video_commands_copy": all("-c:v" not in command or command[command.index("-c:v") + 1] == "copy" for command in manifest["commands"]) if not config.compress else None}
    report["cases"].append(entry)
    print(json.dumps({"case": name, "count": len(infos), "seconds": entry["seconds"], "ok": True}), flush=True)


def count_is(count):
    return lambda result, infos: (_ for _ in ()).throw(AssertionError(f"Expected {count} parts, got {len(infos)}")) if len(infos) != count else None


try:
    check("full_stream_copy", JobConfig(), assertion=count_is(1))
    check("clip_and_count_copy", JobConfig(clip=True, clip_start=3, clip_end=11, split=True, split_count=4), assertion=count_is(4))
    check("duration_copy", JobConfig(split=True, split_mode="duration", split_duration=4), assertion=count_is(5))
    check("size_copy", JobConfig(split=True, split_mode="size", split_size_mb=1, size_safe=False))
    check("clip_and_size_copy", JobConfig(clip=True, clip_start=3, clip_end=13, split=True, split_mode="size", split_size_mb=1, size_safe=False))
    check("audio_only_encode", JobConfig(audio_mode="encode", audio_bitrate=96))
    check("remove_audio", JobConfig(audio_mode="none"), source_path=short,
          assertion=lambda result, infos: (_ for _ in ()).throw(AssertionError("Audio not removed")) if infos[0].audio else None)
    for codec, expected in (("h264", "h264"), ("hevc", "hevc"), ("vp9", "vp9"), ("av1", "av1")):
        check("encode_" + codec, JobConfig(compress=True, codec=codec, speed="fast", clip=True, clip_start=1, clip_end=3,
                                          width=160, height=90, audio_mode="encode"),
              assertion=lambda result, infos, expected=expected: (_ for _ in ()).throw(AssertionError(infos[0].video_codec)) if infos[0].video_codec != expected else None)
    check("clip_and_count_encode", JobConfig(compress=True, speed="fast", clip=True, clip_start=3, clip_end=11, split=True, split_count=4,
                                             width=320, height=180, audio_mode="encode"), assertion=count_is(4))
    check("size_encode_safe", JobConfig(compress=True, speed="ultrafast", quality=14, split=True, split_mode="size", split_size_mb=1, size_safe=True,
                                        audio_mode="encode"), assertion=lambda result, infos: (_ for _ in ()).throw(AssertionError("Size limit exceeded")) if any(info.size > 1024**2 for info in infos) else None)
    cancelled = Engine()
    cancelled.progress = lambda data: cancelled.cancel() if data["fraction"] > 0.01 else None
    try:
        cancelled.process(source, JobConfig(compress=True, speed="veryslow"), root / "cancelled", history_root=root / "history")
        raise AssertionError("Cancellation did not stop processing")
    except Cancelled:
        assert not list((root / "cancelled").rglob(".zhendu-*"))
        assert not list((root / "cancelled").rglob("*.mp4"))
    report["cases"].append({"name": "cancel_and_cleanup", "ok": True})
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    report["source_unchanged"] = True
    report["ok"] = True
except Exception as error:
    report["ok"] = False
    report["error"] = str(error)
    raise
finally:
    atomic_json(root / "integration-report.json", report)
