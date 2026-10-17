"""Actual queued outputs, file clipboard, result selection and playback regressions."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
import time
from unittest.mock import patch

from PySide6.QtCore import QMimeData, Qt
from PySide6.QtMultimedia import QAudioBufferOutput
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from zhendu.config import JobConfig, Store, atomic_json
from zhendu.language import language
from zhendu.ui import MainWindow


def wait_for(predicate, seconds=15):
    deadline = time.monotonic() + seconds
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(50)
    assert predicate(), "Timed out waiting for UI/media state"


root = Path(sys.argv[1]).resolve()
source = str(Path(sys.argv[2]).resolve())
root.mkdir(parents=True, exist_ok=True)
app = QApplication([])
store = Store(root / "config")
window = MainWindow(store)
window.output_dir.setText(str(root / "processed"))
window.show()
report = {"checks": {}}
checks = report["checks"]
clipboard = app.clipboard()
# Keep clipboard data in memory only; never log the user's previous contents.
original = QMimeData()
previous = clipboard.mimeData()
if previous is not None:
    for mime_type in previous.formats():
        original.setData(mime_type, previous.data(mime_type))
try:
    checks["initial_cancel_disabled"] = not window.cancel_button.isEnabled()
    window.add_files([source])
    wait_for(lambda: window.player.play_button.isEnabled() and source in window.media_infos)
    window.clip.setChecked(True)
    window.clip_start.setText("00:00:01.000")
    window.clip_end.setText("00:00:03.000")
    editing = window.snapshot()
    window.enqueue([source, source], JobConfig(split=True, split_count=2))
    checks["cancel_during_processing"] = window.cancel_button.text() in {"取消任务", "Cancel tasks"} and window.cancel_button.isEnabled()
    wait_for(lambda: window.worker is None, 45)
    jobs = list(window.jobs.values())
    outputs = window.result_paths(False)
    checks["all_four_real_results"] = len(outputs) == 4 and all(Path(path).is_file() for path in outputs)
    checks["output_rows"] = all(job["item"].childCount() == 2 and job["item"].isExpanded() for job in jobs)
    checks["footer_becomes_copy"] = window.cancel_button.text() in {"复制文件", "Copy files"} and window.cancel_button.isEnabled()
    window.cancel_button.click()
    app.processEvents()
    checks["clipboard_all_file_urls"] = [str(Path(url.toLocalFile()).resolve()) for url in clipboard.mimeData().urls()] == outputs
    # Inspect native CF_HDROP rather than accepting a text-only clipboard.
    user = ctypes.WinDLL("user32", use_last_error=True)
    user.OpenClipboard.argtypes = [wintypes.HWND]
    user.GetClipboardData.argtypes = [wintypes.UINT]
    user.GetClipboardData.restype = wintypes.HANDLE
    shell = ctypes.WinDLL("shell32")
    shell.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
    shell.DragQueryFileW.restype = wintypes.UINT
    assert user.OpenClipboard(None)
    try:
        handle = user.GetClipboardData(15)  # CF_HDROP
        count = shell.DragQueryFileW(handle, 0xFFFFFFFF, None, 0)
        native = []
        for index in range(count):
            size = shell.DragQueryFileW(handle, index, None, 0)
            buffer = ctypes.create_unicode_buffer(size + 1)
            shell.DragQueryFileW(handle, index, buffer, size + 1)
            native.append(str(Path(buffer.value).resolve()))
        checks["native_windows_files_not_path_text"] = native == outputs
    finally:
        user.CloseClipboard()
    effect = bytes(clipboard.mimeData().data('application/x-qt-windows-mime;value="Preferred DropEffect"'))
    checks["copy_not_cut"] = effect == (1).to_bytes(4, "little")
    parent = jobs[0]["item"]
    child = parent.child(0)
    one = outputs[0]
    window.task_tree.setCurrentItem(child)
    window.copy_result_button.click()
    checks["single_file_copy"] = [str(Path(url.toLocalFile()).resolve()) for url in clipboard.mimeData().urls()] == [one]
    parent.setSelected(True)
    jobs[1]["item"].child(0).setSelected(True)
    checks["multi_select_deduplicates"] = len(window.result_paths()) == 3 and len(set(window.result_paths())) == 3
    window.task_tree.clearSelection()
    window.task_tree.setCurrentItem(parent)
    checks["parent_selects_both_parts"] = window.result_paths() == outputs[:2]
    with patch("zhendu.ui.QInputDialog.getItem", return_value=("2. " + Path(outputs[1]).name, True)):
        checks["choose_specific_part"] = window.choose_result() == outputs[1]
    window.task_tree.setCurrentItem(child)
    with patch("zhendu.ui.QDesktopServices.openUrl", return_value=True) as opener:
        window.open_video_button.click()
        checks["opens_system_player_file"] = str(Path(opener.call_args.args[0].toLocalFile()).resolve()) == one
    with patch("zhendu.ui.QDesktopServices.openUrl", return_value=False), patch("zhendu.ui.error_message") as warning:
        window.open_result()
        checks["default_player_failure_explained"] = warning.call_count == 1
    observer = QAudioBufferOutput(window)
    window.player.media.setAudioBufferOutput(observer)
    audio = []
    observer.audioBufferReceived.connect(lambda buffer: audio.append(buffer.isValid()))
    window.preview_result_button.click()
    wait_for(lambda: window.player.play_button.isEnabled() and one in window.media_infos)
    window.player.toggle()
    wait_for(lambda: window.player.frame_count > 5 and any(audio))
    checks["processed_video_plays_with_audio"] = window.player.path == one and not window.player.audio.isMuted()
    checks["preview_leaves_source_config_intact"] = window.snapshot() == editing and len(window.files) == 1
    checks["result_full_range_and_marks_disabled"] = window.player.start == 0 and window.player.end == window.player.duration and not window.player.a_button.isEnabled()
    window.player.fullscreen.click()
    QTest.qWait(250)
    checks["expanded_result_readonly_marks"] = window.player.expanded is not None and not window.player.expanded.a_button.isEnabled()
    window.player.close_expanded()
    window.player.media.pause()
    app.processEvents()
    checks["pause_immediately_after_expanded_keeps_frame"] = window.player.surface.currentWidget() is window.player.poster and not window.player.poster.pixmap().isNull()
    for choice in ("en", "zh_CN"):
        language.selection = choice
        window.retranslate()
        checks["copy_label_" + choice] = window.cancel_button.text() == ("Copy files" if choice == "en" else "复制文件")
    window.grab().save(str(root / "results.png"))
    # Clicking the source which remains selected must still leave result preview.
    item = window.files[source]
    window.file_tree.itemClicked.emit(item, 0)
    wait_for(lambda: window.player.play_button.isEnabled() and window.player.path == source)
    checks["return_source_preserves_ab"] = not window.previewing_result and window.snapshot() == editing and window.player.a_button.isEnabled()
    removed = Path(one)
    contents = removed.read_bytes()
    removed.unlink()
    with patch("zhendu.ui.error_message") as warning:
        window.copy_selected_results()
        window.open_result()
        checks["missing_file_explained_clipboard_unchanged"] = warning.call_count == 2 and [str(Path(url.toLocalFile()).resolve()) for url in clipboard.mimeData().urls()] == [one]
    removed.write_bytes(contents)
    window.enqueue([source], JobConfig())
    checks["next_run_restores_cancel"] = window.cancel_button.text() in {"取消任务", "Cancel tasks"}
    window.cancel_tasks()
    wait_for(lambda: window.worker is None)
    checks["cancel_keeps_prior_outputs_copyable"] = window.cancel_button.isEnabled() and window.result_paths(False) == outputs
    report["ok"] = all(checks.values())
finally:
    # Restore the original clipboard, even when a regression fails.
    clipboard.setMimeData(original)
    app.processEvents()
    ole = ctypes.WinDLL("ole32")
    ole.OleFlushClipboard.restype = ctypes.c_long
    report["clipboard_restored"] = ole.OleFlushClipboard() >= 0
    window.cancel_tasks()
    if window.worker:
        window.worker.wait(5000)
        QTest.qWait(100)
    window.close()
    app.processEvents()
    atomic_json(root / "result-actions.json", report)
assert report.get("ok") and report["clipboard_restored"], report
print("Result actions: native file clipboard, queue selection, system open and audible preview passed.")
