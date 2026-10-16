"""Run two real EXE invocations and verify their preset jobs share one instance."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pefile

from zhendu.config import JobConfig, Store, atomic_json
from zhendu.media import probe
from zhendu.process import Runner, hidden_process_options

exe = Path(sys.argv[1]).resolve()
root = Path(sys.argv[2]).resolve()
source = Path(sys.argv[3]).resolve()
root.mkdir(parents=True, exist_ok=True)
store = Store(root / "config")
store.data["language"] = "en"
store.data["output_dir"] = str(root / "processed")
preset = store.save_preset("Frozen copy and split", JobConfig(split=True, split_count=2, audio_mode="none"), context=False, include_task=True)
environment = dict(os.environ)
environment["ZHENDU_CONFIG_DIR"] = str(store.root)
for name in ("ZHENDU_FFMPEG_DIR", "PYTHONPATH", "PYTHONHOME"):
    environment.pop(name, None)
environment["PATH"] = str(Path(environment.get("SYSTEMROOT", "C:/Windows")) / "System32")
args = [str(exe), "--preset", preset["id"], "--run", str(source)]
report = {"checks": {}}
log = (root / "process.log").open("w", encoding="utf-8")
primary = subprocess.Popen(args, cwd=root, env=environment, stdout=log, stderr=log, **hidden_process_options())
secondary = None
try:
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and not list(store.root.glob("*.lock")):
        assert primary.poll() is None, "EXE did not stay running"
        time.sleep(0.1)
    secondary = subprocess.Popen(args, cwd=root, env=environment, stdout=log, stderr=log, **hidden_process_options())
    report["checks"]["second_invocation_exits"] = secondary.wait(timeout=25) == 0
    deadline = time.monotonic() + 45
    manifests = []
    while time.monotonic() < deadline:
        assert primary.poll() is None, "Primary EXE exited unexpectedly"
        manifests = list((root / "processed").glob("*/task.json"))
        if len(manifests) >= 2:
            break
        time.sleep(0.15)
    report["checks"]["both_jobs_complete"] = len(manifests) == 2
    jobs = [json.loads(path.read_text(encoding="utf-8")) for path in manifests]
    report["checks"]["two_parts_each"] = len(jobs) == 2 and all(len(job["outputs"]) == 2 for job in jobs)
    report["checks"]["video_copy"] = all(all(command[command.index("-c:v") + 1] == "copy" for command in job["commands"] if "-c:v" in command) for job in jobs)
    report["checks"]["no_old_ab"] = all(not job["settings"]["clip"] and job["settings"]["clip_start"] == 0 for job in jobs)
    outputs = [path.parent / info["file"] for path, job in zip(manifests, jobs) for info in job["outputs"]]
    runner = Runner()
    for output in outputs:
        assert probe(output).video_codec == "h264"
        assert not probe(output).audio
        runner.capture([str(exe.parent / "ffmpeg" / "bin" / "ffmpeg.exe"), "-v", "error", "-i", str(output), "-f", "null", "-"], timeout=30)
    report["checks"]["all_outputs_decode"] = len(outputs) == 4
    report["checks"]["windows_gui_subsystem"] = pefile.PE(str(exe)).OPTIONAL_HEADER.Subsystem == 2
    report["checks"]["ffplay_omitted"] = not (exe.parent / "ffmpeg" / "bin" / "ffplay.exe").exists()
    report["ok"] = all(report["checks"].values())
finally:
    if secondary and secondary.poll() is None:
        secondary.terminate()
        secondary.wait(timeout=10)
    if primary.poll() is None:
        primary.terminate()
        primary.wait(timeout=10)
    log.close()
    atomic_json(root / "frozen-jobs.json", report)
assert report["ok"], report
print("Packaged EXE preset, repeated launch and both stream-copy jobs passed.")
