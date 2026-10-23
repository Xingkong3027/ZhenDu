"""Real Qt input, per-source settings, repeated batches and source outcomes."""
from dataclasses import asdict
from pathlib import Path
import sys
import time
from unittest.mock import patch

from PySide6.QtCore import QPoint, Qt
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from zhendu.config import JobConfig, Store, atomic_json
from zhendu.language import UserError, language
from zhendu.source_settings import config_from_draft
from zhendu.ui import MainWindow


def wait_for(predicate, seconds=20):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(50)
    assert predicate(), "Timed out waiting for Qt/task state"


root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=True)
long, short = [str(Path(path).resolve()) for path in sys.argv[2:4]]
app = QApplication([])
language.selection = "zh_CN"
window = MainWindow(Store(root / "config"))
window.output_dir.setText(str(root / "processed"))
window.show()
report = {"checks": {}}
checks = report["checks"]


def select(path):
    window.file_tree.setCurrentItem(window.files[path])
    window.select_preview(window.files[path], None)
    wait_for(lambda: window.player.path == path and window.player.play_button.isEnabled() and path in window.media_infos)


def click_position(slider, fraction):
    point = QPoint(round((slider.width() - 16) * fraction + 8), slider.height() // 2)
    QTest.mouseClick(slider, Qt.MouseButton.LeftButton, pos=point)


try:
    window.add_files([long, short])
    select(long)
    checks["sync_defaults_and_visible"] = [check.isChecked() for check in window.sync_checks.values()] == [True, False, False] and all(not check.isHidden() for check in window.sync_checks.values())
    actual_output = window.output_dir.text()
    window.output_dir.setText("D:/Videos/Processed")
    for choice in ("zh_CN", "en"):
        language.selection = choice
        window.retranslate()
        QTest.qWait(150)
        window.grab().save(str(root / ("main-" + choice + ".png")))
    language.selection = "zh_CN"
    window.retranslate()
    window.output_dir.setText(actual_output)
    window.quality.setValue(27)
    window.clip.setChecked(True)
    window.clip_start.setText("2")
    window.clip_end.setText("8")
    window.split.setChecked(True)
    window.split_count.setValue(2)
    select(short)
    checks["compression_shared_trim_split_independent"] = window.quality.value() == 27 and not window.clip.isChecked() and not window.split.isChecked()
    window.clip.setChecked(True)
    window.clip_start.setText("1")
    window.clip_end.setText("3")
    select(long)
    checks["source_switch_restores_settings"] = window.snapshot().clip_start == 2 and window.snapshot().clip_end == 8 and window.split.isChecked()
    window.sync_checks["compression"].setChecked(False)
    window.quality.setValue(31)
    select(short)
    checks["compression_sync_off_is_independent"] = window.quality.value() == 27
    window.sync_checks["split"].setChecked(True)
    window.split.setChecked(True)
    window.split_count.setValue(3)
    select(long)
    checks["split_sync_on_applies_current_and_updates"] = window.split.isChecked() and window.split_count.value() == 3
    window.sync_checks["split"].setChecked(False)
    window.split_count.setValue(2)
    window.sync_checks["clip"].setChecked(True)
    window.reset_range()
    select(short)
    checks["synced_full_end_is_per_video"] = window.clip_start.text() == "00:00:00.000" and window.clip_end.text() == "" and window.snapshot().bounds(4) == (0, 4)
    window.sync_checks["clip"].setChecked(False)
    window.clip_start.setText("1")
    window.clip_end.setText("3")
    window.split.setChecked(False)
    checks["disabled_split_labels_and_controls"] = not window.split_mode.isEnabled() and not window.split_form.labelForField(window.split_mode).isEnabled() and not window.split_form.labelForField(window.split_count).isEnabled()
    window.tabs.setCurrentIndex(2)
    app.processEvents()
    window.grab().save(str(root / "split-disabled.png"))
    window.split.setChecked(True)
    for mode, visible in (("count", window.split_count), ("duration", window.split_duration), ("size", window.split_size)):
        window.split_mode.setCurrentIndex(window.split_mode.findData(mode))
        checks["only_active_split_row_" + mode] = all(widget.isVisible() == (widget is visible) for widget in (window.split_count, window.split_duration, window.split_size)) and window.size_safe.isVisible() == (mode == "size")
    window.split_mode.setCurrentIndex(window.split_mode.findData("count"))
    window.split_duration.setText("unfinished")
    window.snapshot()
    window.split_mode.setCurrentIndex(window.split_mode.findData("duration"))
    try:
        window.snapshot()
        checks["active_invalid_duration_rejected"] = False
    except UserError:
        checks["active_invalid_duration_rejected"] = True
    select(long)
    select(short)
    checks["unfinished_draft_survives_switch"] = window.split_duration.text() == "unfinished"
    window.split_mode.setCurrentIndex(window.split_mode.findData("count"))
    window.split.setChecked(False)
    select(long)
    window.clip_start.setText("2")
    window.clip_end.setText("8")
    window.sync_checks["compression"].setChecked(True)
    checks["sync_flags_persist"] = Store(window.store.root).data["sync_settings"] == {"compression": True, "clip": False, "split": False}
    slider = window.player.slider
    click_position(slider, 0.75)
    QTest.qWait(250)
    checks["timeline_click_seeks_when_paused"] = abs(window.player.media.position() / window.player.media.duration() - 0.75) < 0.04 and window.player.media.playbackState() != QMediaPlayer.PlaybackState.PlayingState
    QTest.mousePress(slider, Qt.MouseButton.LeftButton, pos=QPoint(slider.width() // 5, slider.height() // 2))
    QTest.mouseMove(slider, QPoint(slider.width() * 2 // 3, slider.height() // 2), 60)
    QTest.mouseRelease(slider, Qt.MouseButton.LeftButton, pos=QPoint(slider.width() * 2 // 3, slider.height() // 2))
    QTest.qWait(250)
    checks["timeline_drag_from_groove"] = abs(window.player.media.position() / window.player.media.duration() - 2 / 3) < 0.04 and not window.player.dragging
    window.player.toggle()
    click_position(slider, 0.3)
    QTest.qWait(150)
    checks["timeline_preserves_playing_state"] = window.player.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState
    window.player.media.pause()
    window.player.fullscreen.click()
    QTest.qWait(150)
    click_position(window.player.expanded.slider, 0.6)
    QTest.qWait(200)
    checks["expanded_timeline_click_seeks"] = abs(window.player.media.position() / window.player.media.duration() - 0.6) < 0.04
    window.player.close_expanded()
    # One invalid selected source must prevent any partial batch submission.
    window.clip_end.setText("1")
    select(short)
    with patch("zhendu.ui.error_message") as warning:
        window.start_processing()
        checks["validate_all_sources_before_enqueue"] = not window.jobs and warning.call_count == 1 and Path(long).name in str(warning.call_args.args[1])
    select(long)
    window.clip_end.setText("8")
    window.start_processing()
    checks["first_batch_starts_at_zero"] = window.progress_bar.value() == 0
    captured = [asdict(window.jobs[key]["task"].config) for key in window.batch_ids]
    checks["per_source_configs_snapshotted"] = len(captured) == 2 and captured[0]["split_count"] == 2 and captured[0]["clip_start"] == 2 and captured[1]["clip_start"] == 1 and not captured[1]["split"]
    window.clip_end.setText("7")
    checks["queued_settings_do_not_change"] = [asdict(window.jobs[key]["task"].config) for key in window.batch_ids] == captured
    wait_for(lambda: window.worker is None, 45)
    jobs = [window.jobs[key] for key in window.batch_ids]
    checks["both_real_jobs_complete"] = all(job["status"] == "complete" for job in jobs)
    checks["two_parts_and_one_video"] = [len(job["result"].outputs) for job in jobs] == [2, 1]
    checks["successful_sources_auto_removed"] = not window.files and not window.source_settings.sources and not window.active_source
    checks["first_batch_completes_at_100"] = window.progress_bar.value() == 1000
    window.task_tree.setCurrentItem(jobs[0]["item"].child(0))
    menu = window.create_result_menu()
    menu.popup(window.mapToGlobal(QPoint(500, 300)))
    app.processEvents()
    snapshot = menu.grab()
    snapshot.save(str(root / "dark-menu.png"))
    color = snapshot.toImage().pixelColor(3, 3)
    checks["context_menu_dark_background"] = max(color.red(), color.green(), color.blue()) < 100
    menu_image = snapshot.toImage()
    checks["context_menu_readable_text"] = sum(1 for y in range(menu_image.height()) for x in range(menu_image.width()) if min(menu_image.pixelColor(x, y).getRgb()[:3]) > 170) > 30
    task_image = window.task_tree.viewport().grab(window.task_tree.visualItemRect(jobs[0]["item"].child(0))).toImage()
    checks["selected_result_text_has_contrast"] = sum(1 for y in range(task_image.height()) for x in range(task_image.width()) if min(task_image.pixelColor(x, y).getRgb()[:3]) > 170) > 20
    menu.close()
    menu.deleteLater()
    window.add_files([short])
    select(short)
    checks["new_source_has_clean_trim_and_split"] = not window.clip.isChecked() and not window.split.isChecked()
    window.start_processing()
    checks["new_batch_starts_at_zero_with_history"] = window.progress_bar.value() == 0 and len(window.batch_ids) == 1 and len(window.jobs) == 3
    identifier = window.batch_ids[0]
    window.job_progress(identifier, {"fraction": 0.1, "stage": "test"})
    checks["new_batch_progress_excludes_history"] = window.progress_bar.value() == 100
    wait_for(lambda: window.worker is None, 30)
    checks["new_batch_summary_excludes_history"] = "完成 1" in window.progress_label.text() and "完成 3" not in window.progress_label.text()
    checks["history_outputs_remain_copyable"] = len(window.result_paths(False)) == 4
    checks["footer_copies_only_current_round"] = len(window.result_paths(False, current_batch=True)) == 1
    broken = root / "failed video.mp4"
    broken.write_bytes(b"not a video")
    failed_path = str(broken)
    window.add_files([failed_path])
    window.start_processing()
    wait_for(lambda: window.worker is None, 30)
    item = window.files[failed_path]
    checks["failed_source_unchecked_red_and_retained"] = item.checkState(0) == Qt.CheckState.Unchecked and item.foreground(0).color().name() == "#ff928a"
    checks["failed_round_cannot_copy_old_outputs"] = not window.cancel_button.isEnabled()
    language.selection = "en"
    window.retranslate()
    checks["english_sync_label"] = all(check.text() == "Sync settings" for check in window.sync_checks.values())
    checks["finished_summary_translates"] = "failed 1" in window.progress_label.text()
    QTest.qWait(150)
    source_image = window.file_tree.viewport().grab(window.file_tree.visualItemRect(item)).toImage()
    checks["selected_failure_is_visibly_red"] = sum(1 for y in range(source_image.height()) for x in range(source_image.width()) if source_image.pixelColor(x, y).red() > 170 and source_image.pixelColor(x, y).red() > source_image.pixelColor(x, y).green() * 1.4) > 20
    window.grab().save(str(root / "failed-source-en.png"))
    language.selection = "zh_CN"
    window.retranslate()
    broken.write_bytes(Path(short).read_bytes())
    before = len(window.jobs)
    window.retry_failed()
    checks["retry_resets_progress_and_marks_active"] = window.progress_bar.value() == 0 and window.files[failed_path].checkState(0) == Qt.CheckState.Checked
    wait_for(lambda: window.worker is None, 30)
    checks["retry_success_removes_source"] = failed_path not in window.files and len(window.jobs) == before + 1
    window.retry_failed()
    checks["old_failure_not_retried_twice"] = len(window.jobs) == before + 1
    # Manual reprocessing also resolves its previous failed entry.
    broken.write_bytes(b"not a video again")
    window.add_files([failed_path])
    window.start_processing()
    wait_for(lambda: window.worker is None)
    broken.write_bytes(Path(short).read_bytes())
    window.files[failed_path].setCheckState(0, Qt.CheckState.Checked)
    window.start_processing()
    wait_for(lambda: window.worker is None)
    before_manual_retry = len(window.jobs)
    window.retry_failed()
    checks["manual_correction_retires_old_failure"] = len(window.jobs) == before_manual_retry and failed_path not in window.files
    window.add_files([short])
    select(short)
    window.enqueue([short, short], JobConfig())
    window.cancel_tasks()
    wait_for(lambda: window.worker is None)
    checks["cancelled_source_retained_unchecked"] = short in window.files and window.files[short].checkState(0) == Qt.CheckState.Unchecked
    window.file_tree.setCurrentItem(window.files[short])
    window.remove_files()
    checks["manual_removal_clears_source_state"] = not window.files and not window.source_settings.sources
    report["ok"] = all(checks.values())
finally:
    window.cancel_tasks()
    if window.worker:
        window.worker.wait(8000)
        QTest.qWait(100)
    window.close()
    app.processEvents()
    atomic_json(root / "batch-experience.json", report)
assert report.get("ok"), report
print("Batch experience:", len(checks), "checks passed.")
