from dataclasses import asdict, dataclass
from datetime import datetime
import json
import math
from pathlib import Path
import shutil
import subprocess
import time
import uuid

from .config import JobConfig, atomic_json, safe_name
from .language import UserError, t
from .media import ProbeCache, number, probe, video_span
from .paths import media_binary
from .process import Runner


@dataclass
class Result:
    directory: str
    outputs: list[str]
    elapsed: float
    input_size: int
    output_size: int


def encoder_for(config, available=None):
    cpu = {"h264": "libx264", "hevc": "libx265", "vp9": "libvpx-vp9", "av1": "libaom-av1"}
    if config.backend == "cpu":
        if config.codec == "av1" and available and "libsvtav1" in available:
            return "libsvtav1"
        return cpu[config.codec]
    if config.codec == "vp9" and config.backend != "qsv":
        raise UserError("VP9 硬件编码仅提供 Intel QSV；请改用 CPU。", "VP9 hardware encoding is available through Intel QSV; choose CPU otherwise.")
    return config.codec + "_" + config.backend


def output_extension(config, source):
    if config.container != "auto":
        return "." + config.container
    if config.compress:
        return {"h264": ".mp4", "hevc": ".mp4", "vp9": ".webm", "av1": ".mkv"}[config.codec]
    extension = Path(source).suffix.lower()
    return extension if extension in {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".ts", ".mts", ".m2ts", ".flv", ".wmv", ".mpg", ".mpeg"} else ".mkv"


def encoding_args(config, info, extension, available=None):
    args = ["-map", f"0:{info.video_index}"]
    if config.audio_mode != "none":
        selector = "0:a?" if config.audio_track < 0 else f"0:a:{config.audio_track}?"
        args += ["-map", selector]
    if config.subtitles:
        args += ["-map", "0:s?", "-c:s", "copy"]
    args += ["-map_metadata", "0", "-map_chapters", "-1" if config.clip or config.split else "0"]
    if not config.compress:
        args += ["-c:v", "copy"]
    else:
        encoder = encoder_for(config, available)
        quality = min(config.quality, 51 if config.codec in {"h264", "hevc"} else 63)
        args += ["-c:v", encoder]
        speeds = {"ultrafast": 0, "veryfast": 1, "fast": 2, "medium": 3, "slow": 4, "veryslow": 5}
        speed_index = speeds[config.speed]
        if encoder in {"libx264", "libx265"}:
            args += ["-preset", config.speed, "-crf", str(quality)]
        elif encoder == "libsvtav1":
            args += ["-preset", str([12, 10, 8, 6, 4, 2][speed_index]), "-crf", str(quality)]
        elif encoder in {"libaom-av1", "libvpx-vp9"}:
            args += ["-cpu-used", str([8, 7, 5, 3, 2, 0][speed_index]), "-crf", str(quality), "-b:v", "0"]
            if encoder == "libvpx-vp9":
                args += ["-deadline", "good", "-row-mt", "1"]
        elif config.backend == "nvenc":
            args += ["-preset", ["p1", "p2", "p3", "p4", "p6", "p7"][speed_index], "-rc", "vbr", "-cq", str(quality), "-b:v", "0"]
        elif config.backend == "qsv":
            args += ["-preset", ["veryfast", "veryfast", "fast", "medium", "slow", "veryslow"][speed_index], "-global_quality", str(quality)]
        elif config.backend == "amf":
            args += ["-quality", "speed" if speed_index < 2 else "balanced" if speed_index < 4 else "quality", "-rc", "cqp"]
            args += ["-qp_i", str(quality), "-qp_p", str(quality)]
        filters = []
        if config.width or config.height or config.color_range != "source":
            scale = f"scale={config.width or -2}:{config.height or -2}" if config.width or config.height else "scale=iw:ih"
            if config.color_range != "source":
                scale += ":in_range=auto:out_range=" + ("tv" if config.color_range == "limited" else "pc")
                args += ["-color_range", "tv" if config.color_range == "limited" else "pc"]
            filters.append(scale)
        if filters:
            args += ["-vf", ",".join(filters)]
        if config.fps:
            args += ["-r", f"{config.fps:g}"]
    if config.audio_mode == "copy":
        args += ["-c:a", "copy"]
    elif config.audio_mode == "encode":
        args += ["-c:a", "libopus" if extension == ".webm" else "aac", "-b:a", f"{config.audio_bitrate}k"]
    else:
        args += ["-an"]
    return args


class Engine:
    def __init__(self, cache=None, progress=lambda value: None, log=lambda message: None):
        self.cache = cache or ProbeCache()
        self.progress = progress
        self.log = log
        self.runner = Runner(log)
        self.available = None
        self.checked_encoders = set()
        self.commands = []

    def cancel(self):
        self.runner.cancel()

    def encoders(self):
        if self.available is None:
            text = self.runner.capture([media_binary("ffmpeg.exe"), "-hide_banner", "-encoders"])
            self.available = {parts[1] for line in text.splitlines() if len(parts := line.split()) > 1 and len(parts[0]) == 6}
        return self.available

    def preflight(self, config, info, extension):
        if config.compress:
            encoder = encoder_for(config, self.encoders())
            if encoder not in self.encoders():
                raise UserError("当前 FFmpeg 不包含编码器 {encoder}。", "This FFmpeg build does not include {encoder}.", encoder=encoder)
            if config.backend != "cpu" and encoder not in self.checked_encoders:
                try:
                    self.runner.capture([media_binary("ffmpeg.exe"), "-v", "error", "-f", "lavfi", "-i", "color=black:s=128x128:r=1",
                                         "-frames:v", "1", "-c:v", encoder, "-f", "null", "-"], timeout=25)
                except RuntimeError as error:
                    raise UserError("硬件编码器 {encoder} 无法使用，请检查显卡/驱动或选择 CPU。\n{detail}",
                                    "Hardware encoder {encoder} is unavailable. Check your GPU/driver or choose CPU.\n{detail}",
                                    encoder=encoder, detail=str(error)) from error
                self.checked_encoders.add(encoder)
        video_codec = config.codec if config.compress else info.video_codec
        if extension == ".webm" and video_codec not in {"vp8", "vp9", "av1"}:
            raise UserError("WebM 仅适合 VP8、VP9 或 AV1；请选择自动或 MKV 容器。", "WebM requires VP8, VP9 or AV1. Choose Auto or MKV.")
        selected = info.audio if config.audio_track < 0 else info.audio[config.audio_track:config.audio_track + 1]
        if config.audio_mode != "none" and config.audio_track >= len(info.audio) and config.audio_track >= 0:
            raise UserError("选定音轨在该视频中不存在。", "The selected audio track does not exist in this video.")
        if config.audio_mode == "copy" and extension == ".webm" and any(audio.get("codec_name") not in {"opus", "vorbis"} for audio in selected):
            raise UserError("源音频不能直接复制到 WebM，请选择音频转码或 MKV。", "The source audio cannot be copied into WebM. Choose audio encoding or MKV.")

    def base(self):
        return [media_binary("ffmpeg.exe"), "-hide_banner", "-loglevel", "warning", "-nostdin", "-y", "-nostats", "-progress", "pipe:1"]

    def emit(self, fraction, stage, **stats):
        self.progress({"fraction": min(max(fraction, 0.0), 0.995), "stage": stage, **stats})

    def run_ffmpeg(self, args, duration, base=0.0, span=1.0, stage=None):
        stage = stage or t("处理中", "Processing")
        self.commands.append([str(arg) for arg in args])
        self.log(subprocess.list2cmdline([str(arg) for arg in args]))
        values = {}
        for line in self.runner.lines(args):
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value
            if key == "progress":
                position = number(values.get("out_time_us")) / 1000000
                self.emit(base + span * min(max(position / duration, 0), 1) if duration else base, stage,
                          position=position, speed=values.get("speed", ""), fps=values.get("fps", ""),
                          size=number(values.get("total_size")))

    def input_args(self, source, start=0.0):
        return (["-ss", f"{start:.6f}"] if start > 0 else []) + ["-i", str(source)]

    def single_or_timed(self, source, config, info, stage_dir, extension, start, length):
        args = self.base() + self.input_args(source, start) + encoding_args(config, info, extension, self.available)
        args += ["-t", f"{length:.6f}"]
        if not config.compress:
            args += ["-avoid_negative_ts", "make_zero"]
        stem = safe_name(Path(source).stem)
        if not config.split:
            output = stage_dir / (stem + extension)
            if extension in {".mp4", ".mov", ".m4v"}:
                args += ["-movflags", "+faststart"]
            self.run_ffmpeg(args + [str(output)], length)
            return [output]
        if config.split_mode == "count":
            interval = length / config.split_count
            cuts = ",".join(f"{interval * index:.6f}" for index in range(1, config.split_count))
            segment_args = ["-segment_times", cuts]
            force = cuts
        else:
            interval = config.split_duration
            segment_args = ["-segment_time", f"{interval:.6f}"]
            force = f"expr:gte(t,n_forced*{interval:.6f})"
        if config.compress:
            args += ["-force_key_frames", force]
        args += ["-f", "segment", "-reset_timestamps", "1", "-segment_start_number", "1", "-reference_stream", "v:0"]
        fps = config.fps or info.fps
        if fps:
            args += ["-segment_time_delta", f"{0.5 / fps:.9f}"]
        pattern = stage_dir / (stem + "_part%03d" + extension)
        self.run_ffmpeg(args + segment_args + [str(pattern)], length, stage=t("截取后分割" if config.clip else "分割中", "Trimming and splitting" if config.clip else "Splitting"))
        return sorted(stage_dir.glob(stem + "_part*" + extension))

    def scan_cuts(self, source, info, target, safe, base=0.0):
        # Stream the packet list: memory does not grow with video length.
        args = [media_binary("ffprobe.exe"), "-v", "error", "-show_packets", "-show_entries",
                "packet=stream_index,pts_time,dts_time,size,flags", "-of", "compact=p=0:nk=0", str(source)]
        effective = target * (0.70 if safe and target < 8 * 1024**2 else 0.88 if safe and target < 32 * 1024**2 else 0.96 if safe else 0.99)
        total, origin, last_time, previous = 0, 0, 0.0, None
        cuts = []
        last_ui = 0.0
        for line in self.runner.lines(args):
            fields = dict(item.split("=", 1) for item in line.split("|") if "=" in item)
            total += int(number(fields.get("size")))
            pts = number(fields.get("pts_time"), number(fields.get("dts_time"), None))
            if pts is not None:
                pts -= info.start_time
            key = int(number(fields.get("stream_index"), -1)) == info.video_index and "K" in fields.get("flags", "") and pts is not None and pts > last_time + 0.02
            if safe and total - origin >= effective and previous and previous[0] > last_time + 0.02:
                last_time, origin = previous
                cuts.append(last_time)
                previous = None
            if key:
                current = (pts, total)
                if total - origin >= effective:
                    chosen = current
                    if previous and abs(previous[1] - origin - effective) <= abs(total - origin - effective):
                        chosen = previous
                    if chosen[0] > last_time + 0.02:
                        last_time, origin = chosen
                        cuts.append(last_time)
                    previous = current if chosen != current else None
                else:
                    previous = current
            if time.monotonic() - last_ui > 0.2:
                last_ui = time.monotonic()
                self.emit(base + 0.15 * min(total / max(info.size, 1), 1), t("分析大小分割点", "Analyzing size boundaries"))
        return [value for value in cuts if 0.02 < value < info.duration - 0.02]

    def size_copy(self, source, config, info, stage_dir, extension, start, length):
        original_stem = safe_name(Path(source).stem)
        scan_source, scan_info = source, info
        scan_base = 0.0
        if config.clip:
            # Size analysis uses the actual copied range and its new timestamps.
            # This remuxes only the selected range and never encodes video/audio.
            scan_source = stage_dir / ".selected_range.mkv"
            args = self.base() + self.input_args(source, start) + ["-map", f"0:{info.video_index}", "-map", "0:a?"]
            if config.subtitles:
                args += ["-map", "0:s?"]
            args += ["-c", "copy"]
            self.run_ffmpeg(args + ["-t", f"{length:.6f}", "-avoid_negative_ts", "make_zero", str(scan_source)], length,
                            span=0.15, stage=t("准备截取范围（流复制）", "Preparing trim range (stream copy)"))
            scan_info = probe(scan_source, self.runner)
            scan_base = 0.15
        target = int(config.split_size_mb * 1024**2)
        cuts = self.scan_cuts(scan_source, scan_info, target, config.size_safe, scan_base)
        args = self.base() + ["-i", str(scan_source)] + encoding_args(config, scan_info, extension)
        pattern = stage_dir / (original_stem + "_part%03d" + extension)
        if cuts:
            args += ["-f", "segment", "-segment_times", ",".join(f"{value:.6f}" for value in cuts), "-reset_timestamps", "1",
                     "-segment_start_number", "1", "-reference_stream", "v:0"]
            if scan_info.fps:
                args += ["-segment_time_delta", f"{0.5 / scan_info.fps:.9f}"]
            output = str(pattern)
        else:
            output = str(pattern).replace("%03d", "001")
        self.run_ffmpeg(args + [output], scan_info.duration, base=scan_base + 0.15, span=0.85 - scan_base,
                        stage=t("快速大小分割", "Fast size splitting"))
        outputs = sorted(stage_dir.glob(original_stem + "_part*" + extension))
        maximum = max((path.stat().st_size for path in outputs), default=0)
        if maximum > target:
            if config.size_safe:
                raise UserError("流复制分段超出上限（最大 {size:.2f} MiB）。单个关键帧间隔可能过大，请提高上限或改为压缩。",
                                "A copied segment exceeds the limit ({size:.2f} MiB). A keyframe interval may be too large; increase the limit or enable compression.", size=maximum / 1024**2)
            self.log(t("部分分段超过目标大小：流复制受关键帧限制。", "Some parts exceed the target size because stream copy is limited by keyframes."))
        if config.clip and Path(scan_source).exists():
            Path(scan_source).unlink()
        return outputs

    def size_encode(self, source, config, info, stage_dir, extension, start, length):
        target = int(config.split_size_mb * 1024**2)
        ratio = 0.70 if config.size_safe and target < 8 * 1024**2 else 0.88 if config.size_safe and target < 32 * 1024**2 else 0.96 if config.size_safe else 0.99
        threshold = int(target * ratio)
        position, part, outputs = 0.0, 1, []
        while position < length - 0.04:
            self.runner.check()
            temporary = stage_dir / (".encoding" + extension)
            output = stage_dir / (safe_name(Path(source).stem) + f"_part{part:03d}" + extension)
            attempt_threshold = threshold
            for attempt in range(4 if config.size_safe else 1):
                args = self.base() + self.input_args(source, start + position) + encoding_args(config, info, extension, self.available)
                args += ["-t", f"{length - position:.6f}", "-fs", str(attempt_threshold), "-avoid_negative_ts", "make_zero", str(temporary)]
                self.run_ffmpeg(args, length, base=position / length, span=1, stage=t("大小分割：第 {n} 段", "Size splitting: part {n}", n=part))
                first_pts, duration = video_span(temporary, self.runner)
                if duration < 0.01:
                    raise UserError("分段视频时长异常，已停止以避免重复处理。", "Invalid segment duration; stopped to avoid repeating the same range.")
                trim = self.base() + ["-i", str(temporary), "-map", "0", "-c", "copy", "-t", f"{first_pts + duration:.6f}",
                                      "-avoid_negative_ts", "make_zero", str(output)]
                self.run_ffmpeg(trim, length, base=position / length, span=0, stage=t("对齐分段音视频", "Aligning segment audio and video"))
                size = output.stat().st_size
                if not config.size_safe or size <= target:
                    break
                if attempt == 3:
                    raise UserError("分段重试后仍超过目标大小，请提高上限。", "The part still exceeds the size limit after retries; increase the limit.")
                attempt_threshold = max(256 * 1024, int(attempt_threshold * min(0.85, target / size * 0.92)))
            temporary.unlink(missing_ok=True)
            outputs.append(output)
            position = min(length, position + duration)
            if config.size_safe:
                threshold = min(threshold, attempt_threshold)
            self.emit(position / length, t("大小分割：第 {n} 段已完成", "Size splitting: part {n} complete", n=part))
            part += 1
            if part > 9999:
                raise UserError("分段数超过 9999，请提高目标大小。", "More than 9999 parts; increase the target size.")
        return outputs

    def process(self, source, config, output_root=None):
        config = JobConfig.from_dict(asdict(config))
        source = Path(source).resolve()
        info = self.cache.get(source, self.runner)
        start, end = config.bounds(info.duration)
        extension = output_extension(config, source)
        self.preflight(config, info, extension)
        root = Path(output_root).resolve() if output_root else source.parent / "帧渡输出"
        root.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(root).free < 100 * 1024**2:
            raise UserError("输出磁盘可用空间不足 100 MiB。", "The output disk has less than 100 MiB free.")
        directory = root / (safe_name(source.stem) + "_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6])
        directory.mkdir()
        stage_dir = directory / ".working"
        stage_dir.mkdir()
        started = time.monotonic()
        self.commands = []
        try:
            if config.split and config.split_mode == "size":
                outputs = self.size_encode(source, config, info, stage_dir, extension, start, end - start) if config.compress else self.size_copy(source, config, info, stage_dir, extension, start, end - start)
            else:
                outputs = self.single_or_timed(source, config, info, stage_dir, extension, start, end - start)
            if not outputs:
                raise UserError("没有生成输出视频。", "No output video was created.")
            verified = []
            for output in outputs:
                self.runner.check()
                if not output.is_file() or output.stat().st_size == 0:
                    raise UserError("输出视频为空。", "The output video is empty.")
                output_info = probe(output, self.runner)
                verified.append({"file": output.name, "duration": output_info.duration, "size": output_info.size,
                                 "video_codec": output_info.video_codec, "audio_tracks": len(output_info.audio)})
            self.runner.check()
            published = []
            for output in outputs:
                final = directory / output.name
                output.replace(final)
                published.append(str(final))
            elapsed = time.monotonic() - started
            atomic_json(directory / "task.json", {"app": "ZhenDu", "input": str(source), "settings": asdict(config),
                                                 "requested_range": [start, end], "outputs": verified,
                                                 "elapsed_seconds": elapsed, "commands": self.commands})
            self.progress({"fraction": 1.0, "stage": t("完成", "Complete")})
            return Result(str(directory), published, elapsed, info.size, sum(Path(path).stat().st_size for path in published))
        except Exception as error:
            try:
                atomic_json(directory / "task.failed.json", {"input": str(source), "settings": asdict(config), "error": str(error), "commands": self.commands})
            except OSError:
                pass
            raise
        finally:
            # The staging directory was created exclusively for this job.
            if stage_dir.resolve().parent == directory.resolve() and not stage_dir.is_symlink():
                shutil.rmtree(stage_dir, ignore_errors=True)
