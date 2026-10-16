"""Actual Qt IPC, queue and settings smoke test with isolated configuration."""
from dataclasses import asdict
from pathlib import Path
import sys
import json
import subprocess
import time
import uuid

from zhendu.application import InstanceServer, send_request
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from zhendu.config import JobConfig, Store, atomic_json
from zhendu.language import language
from zhendu.shell import ShellIntegration
from zhendu.process import hidden_process_options
from zhendu.ui import MainWindow, SettingsDialog


class EmptyRegistry:
    def get(self, path, name):
        return None


root = Path(sys.argv[1]).resolve()
source = str(Path(sys.argv[2]).resolve())
app = QApplication([])
store = Store(root / "config")
window = MainWindow(store, ShellIntegration(store, EmptyRegistry()))
window.output_dir.setText(str(root / "processed"))
window.show()
report = {"checks": {}}
try:
    dialog = SettingsDialog(store, window.shell, window)
    report["checks"]["direct_output_default"] = not dialog.task_subfolders.isChecked()
    dialog.task_subfolders.setChecked(True)
    dialog.apply()
    report["checks"]["folder_setting_persists"] = Store(store.root).data["task_subfolders"] is True
    dialog = SettingsDialog(store, window.shell, window)
    dialog.task_subfolders.setChecked(False)
    report["checks"]["language_options"] = [dialog.language_combo.itemData(index) for index in range(3)] == ["auto", "zh_CN", "en"]
    dialog.language_combo.setCurrentIndex(dialog.language_combo.findData("en"))
    dialog.changed.connect(window.retranslate)
    dialog.apply()
    report["checks"]["english_applies"] = window.start_button.text() == "Start processing" and Store(store.root).data["language"] == "en"
    language.selection = "zh_CN"
    window.retranslate()
    preset = store.save_preset("IPC test", JobConfig(audio_mode="none", split=True, split_count=2), include_task=True)
    window.refresh_presets()
    window.clip.setChecked(True)
    window.clip_start.setText("00:00:12.000")
    name = "ZhenDu-Test-" + uuid.uuid4().hex
    server = InstanceServer(window, name)
    for index in range(2):
        request = {"protocol": 1, "files": [source], "preset": preset["id"], "run": True}
        sender = subprocess.Popen([sys.executable, "-B", "-c", "import json,sys; from zhendu.application import send_request; from PySide6.QtCore import QCoreApplication; app=QCoreApplication([]); sys.exit(0 if send_request(sys.argv[1],json.loads(sys.argv[2])) else 1)", name, json.dumps(request)], **hidden_process_options())
        deadline = time.monotonic() + 15
        while sender.poll() is None and time.monotonic() < deadline:
            QTest.qWait(50)
        if sender.poll() is None:
            sender.kill()
        assert sender.wait(timeout=5) == 0, "IPC failed"
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline and (window.worker or len(window.jobs) < 2 or any(job["status"] in {"queued", "running"} for job in window.jobs.values())):
        QTest.qWait(100)
    jobs = list(window.jobs.values())
    report["checks"]["both_ipc_tasks_complete"] = len(jobs) == 2 and all(job["status"] == "complete" for job in jobs)
    report["checks"]["clean_ab_per_request"] = all(not job["task"].config.clip and job["task"].config.clip_start == 0 for job in jobs)
    report["checks"]["preset_split_retained"] = all(job["task"].config.split and job["task"].config.split_count == 2 for job in jobs)
    outputs = [path for job in jobs if job["result"] for path in job["result"].outputs]
    report["checks"]["direct_output_no_collisions"] = len(set(outputs)) == 4 and all(Path(path).parent == root / "processed" for path in outputs)
    report["checks"]["only_videos_in_output"] = len(list((root / "processed").iterdir())) == 4
    report["checks"]["output_mode_snapshotted"] = all(not job["task"].task_subfolders for job in jobs)
    report["checks"]["two_parts_per_task"] = all(job["result"] and len(job["result"].outputs) == 2 for job in jobs)
    report["jobs"] = [{"status": job["status"], "config": asdict(job["task"].config)} for job in jobs]
    report["ok"] = all(report["checks"].values())
finally:
    window.cancel_tasks()
    if window.worker:
        window.worker.wait(5000)
        QTest.qWait(100)
    window.close()
    app.processEvents()
    atomic_json(root / "ui-report.json", report)
assert report["ok"], report
print("Qt settings, IPC and both queued jobs passed.")
