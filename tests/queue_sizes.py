"""Actual growing FFmpeg outputs, queue clearing, errors and late UI signals."""
from pathlib import Path
import sys
import time
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from zhendu.config import JobConfig, Store, atomic_json
from zhendu.engine import Engine
from zhendu.language import language
from zhendu.output_sizes import format_size
from zhendu.ui import MainWindow


def wait_for(predicate, seconds=35):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(40)
    assert predicate(), "Timed out waiting for task state"


root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=True)
source = str(Path(sys.argv[2]).resolve())
app = QApplication([])
language.selection = "zh_CN"
window = MainWindow(Store(root / "config"))
window.output_dir.setText(str(root / "processed"))
window.show()
checks = {}
saved = []
original_input = Engine.input_args


def paced_input(self, *args, **kwargs):
    # Only this test reads at real-time speed, allowing multiple live samples.
    return ["-re"] + original_input(self, *args, **kwargs)


try:
    checks["empty_list_cannot_clear"] = not window.clear_tasks_button.isEnabled()
    window.add_files([source])
    with patch.object(Engine, "input_args", paced_input):
        window.enqueue([source, source], JobConfig(container="mkv", clip=True, clip_end=6,
                                                  split=True, split_mode="duration", split_duration=2))
        ids = list(window.batch_ids)
        checks["queued_clear_disabled"] = not window.clear_tasks_button.isEnabled()
        window.clear_task_list()
        checks["active_clear_guarded"] = len(window.jobs) == 2
        wait_for(lambda: window.jobs[ids[0]]["output_size"] > 0)
        first = window.jobs[ids[0]]
        checks["live_size_before_completion"] = first["status"] == "running" and first["item"].text(3) == format_size(first["output_size"])
        checks["live_parts_sum"] = bool(first["live_parts"]) and sum(first["part_sizes"].values()) == first["output_size"]
        child = first["item"].child(0)
        window.task_tree.setCurrentItem(child)
        window.refresh_result_actions()
        checks["unfinished_files_not_actionable"] = not window.result_paths() and not window.copy_result_button.isEnabled() and not child.data(0, Qt.ItemDataRole.UserRole + 1)
        initial = first["output_size"]
        wait_for(lambda: first["output_size"] > initial)
        checks["size_grows_without_finishing"] = first["status"] == "running"
        wait_for(lambda: first["status"] == "complete")
        checks["next_job_keeps_clear_disabled"] = not window.clear_tasks_button.isEnabled() and window.worker is not None
        wait_for(lambda: window.worker is None)
    checks["both_complete_and_clear_enabled"] = all(window.jobs[key]["status"] == "complete" for key in ids) and window.clear_tasks_button.isEnabled()
    for key in ids:
        job = window.jobs[key]
        sizes = {Path(path).name: Path(path).stat().st_size for path in job["result"].outputs}
        saved.extend(job["result"].outputs)
        checks["final_exact_bytes_" + str(ids.index(key))] = job["output_size"] == sum(sizes.values()) == job["result"].output_size and job["part_sizes"] == sizes
        checks["final_children_" + str(ids.index(key))] = job["item"].childCount() == len(sizes) and all(job["item"].child(i).text(3) == format_size(size) for i, size in enumerate(sizes.values()))
    job = window.jobs[ids[0]]
    original_config, original_parts = job["task"].config, job["part_sizes"]
    original_size = job["output_size"]
    job["task"].config = JobConfig(split=True, split_mode="size", split_size_mb=1)
    job.update(part_sizes={"one": 700000, "two": 700000}, output_size=1400000)
    window.update_job_item(job)
    checks["total_not_mistaken_for_part_overflow"] = "↑" not in job["item"].text(3)
    job["part_sizes"]["one"] = 1100000
    job["output_size"] = 1800000
    window.update_job_item(job)
    checks["single_part_overflow_indicator"] = "↑" in job["item"].text(3)
    job.update(part_sizes=original_parts, output_size=original_size)
    job["task"].config = original_config
    window.update_job_item(job)
    window.job_progress(ids[0], {"fraction": .2, "stage": "late", "output_size": 8})
    checks["late_progress_cannot_rewrite_final_size"] = job["output_size"] == original_size
    # Verify both languages and narrow desktop layouts with real result rows.
    for choice, header, label in (("zh_CN", "输出大小", "清空列表"), ("en", "Output size", "Clear list")):
        language.selection = choice
        window.retranslate()
        checks["language_" + choice] = window.task_tree.headerItem().text(3) == header and window.clear_tasks_button.text() == label
        window.resize(980, 700)
        QTest.qWait(80)
        checks["clear_visible_" + choice] = window.clear_tasks_button.isVisible() and window.clear_tasks_button.geometry().right() < window.clear_tasks_button.parentWidget().width()
        window.grab().save(str(root / ("queue-" + choice + ".png")))
    language.selection = "zh_CN"
    window.retranslate()
    window.add_files([source])
    window.clear_tasks_button.click()
    checks["clear_resets_records_progress_actions"] = not window.jobs and not window.batch_ids and window.task_tree.topLevelItemCount() == 0 and window.progress_bar.value() == 0 and not window.clear_tasks_button.isEnabled() and not window.copy_result_button.isEnabled() and not window.cancel_button.isEnabled()
    checks["clear_preserves_sources_and_files"] = source in window.files and all(Path(path).is_file() for path in saved)
    window.job_progress(ids[0], {"fraction": .5, "stage": "late", "output_size": 8})
    checks["late_progress_ignored"] = not window.jobs and window.progress_bar.value() == 0
    with patch.object(Engine, "input_args", paced_input):
        window.enqueue([source], JobConfig(container="mkv"))
        checks["new_round_zero"] = window.progress_bar.value() == 0
        key = window.batch_ids[0]
        wait_for(lambda: window.jobs[key]["output_size"] > 0)
        window.cancel_tasks()
        checks["cancel_pending_still_cannot_clear"] = not window.clear_tasks_button.isEnabled()
        wait_for(lambda: window.worker is None)
    checks["cancel_not_claimed_as_output"] = window.jobs[key]["status"] == "cancelled" and window.jobs[key]["item"].text(3) == "—" and window.jobs[key]["item"].childCount() == 0 and window.clear_tasks_button.isEnabled()
    window.clear_task_list()
    window.enqueue([str(root / "missing.mp4")], JobConfig())
    wait_for(lambda: window.worker is None)
    checks["failed_can_clear_no_output"] = window.clear_tasks_button.isEnabled() and window.jobs[window.batch_ids[0]]["item"].text(3) == "—"
    window.clear_task_list()
    atomic_json(root / "queue-sizes.json", {"checks": checks, "passed": sum(checks.values()), "total": len(checks)})
    assert all(checks.values()), [key for key, value in checks.items() if not value]
    print(f"Queue sizes: {len(checks)} checks passed")
finally:
    if window.worker:
        window.cancel_tasks()
        wait_for(lambda: window.worker is None)
    window.player.media.stop()
    window.player.media.setSource("")
    window.close()
    app.processEvents()
