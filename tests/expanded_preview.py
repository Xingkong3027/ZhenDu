"""Exercise full-screen preview with actual playback, controls and exits."""
from pathlib import Path
import sys
import time

from zhendu.application import QApplication
from PySide6.QtCore import Qt
from PySide6.QtMultimedia import QAudioBufferOutput, QMediaPlayer
from PySide6.QtTest import QTest

from zhendu.config import Store, atomic_json
from zhendu.language import language
from zhendu.shell import ShellIntegration
from zhendu.ui import MainWindow
from zhendu.window_theme import install_window_theme


class EmptyRegistry:
    def get(self, path, name):
        return None


root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=True)
app = QApplication([])
install_window_theme(app)
store = Store(root / "config")
window = MainWindow(store, ShellIntegration(store, EmptyRegistry()))
window.show()
player = window.player
report = {"checks": {}}
audio = {"buffers": 0}
observer = QAudioBufferOutput(window)
observer.audioBufferReceived.connect(lambda buffer: audio.update(buffers=audio["buffers"] + int(buffer.isValid())))
player.media.setAudioBufferOutput(observer)
player.volume.setValue(15)


def wait_until(condition, seconds=5):
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        QTest.qWait(50)
    assert condition(), "Timed out waiting for preview"


try:
    window.add_files([str(Path(sys.argv[2]).resolve())])
    wait_until(lambda: player.play_button.isEnabled() and player.duration > 0)
    player.media.setPosition(1500)
    QTest.qWait(250)
    screen_size = window.screen().geometry().size()
    original_geometry = player.surface.geometry()
    before_position = player.media.position()
    player.fullscreen.click()
    expanded = player.expanded
    assert expanded is not None
    QTest.qWait(250)
    report["checks"]["full_screen_host"] = expanded.isFullScreen() and not expanded.video.isFullScreen()
    report["checks"]["screen_resolution_unchanged"] = window.screen().geometry().size() == screen_size
    report["checks"]["same_player_and_source"] = player.media.videoOutput() is expanded.video and player.media.position() == before_position
    report["checks"]["preview_fills_layout"] = expanded.surface.height() > 500 and expanded.poster.geometry() == expanded.surface.rect()
    report["checks"]["controls_visible"] = all(widget.isVisible() for widget in (expanded.slider, expanded.time_label, expanded.play_button, expanded.exit_button, expanded.volume))
    report["checks"]["paused_poster_centered"] = expanded.surface.currentWidget() is expanded.poster and expanded.poster.alignment() == Qt.AlignmentFlag.AlignCenter and not expanded.poster.pixmap().isNull()
    expanded.grab().save(str(root / "expanded-paused.png"))
    language.selection = "en"
    window.retranslate()
    QTest.qWait(100)
    report["checks"]["english_controls"] = expanded.exit_button.text() == "Exit expanded view · Esc" and expanded.play_button.text() == "Play"
    language.selection = "zh_CN"
    window.retranslate()
    first_frames, first_audio = player.frame_count, audio["buffers"]
    expanded.play_button.click()
    wait_until(lambda: player.frame_count > first_frames + 8)
    report["checks"]["playing_video_fills_layout"] = expanded.video.geometry() == expanded.surface.rect()
    report["checks"]["playing_frames_and_audio"] = audio["buffers"] > first_audio and player.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState
    QTest.keyClick(expanded, Qt.Key.Key_Space)
    QTest.qWait(120)
    report["checks"]["space_pauses"] = player.media.playbackState() == QMediaPlayer.PlaybackState.PausedState
    expanded.slider.sliderPressed.emit()
    expanded.slider.setValue(2400)
    expanded.slider.sliderMoved.emit(2400)
    expanded.slider.sliderReleased.emit()
    QTest.qWait(250)
    report["checks"]["seek_and_seconds"] = abs(player.media.position() - 2400) < 150 and "02.400" in expanded.time_label.text()
    expanded.volume.setValue(37)
    expanded.mute.setChecked(True)
    report["checks"]["shared_sound_controls"] = player.audio.isMuted() and abs(player.audio.volume() - 0.37) < 0.001
    expanded.mute.setChecked(False)
    expanded.exit_button.click()
    QTest.qWait(150)
    report["checks"]["button_exit_restores_embedded_preview"] = player.expanded is None and player.media.videoOutput() is player.video and player.surface.geometry() == original_geometry and abs(player.media.position() - 2400) < 150
    for index, key in enumerate((Qt.Key.Key_Escape, Qt.Key.Key_F11)):
        player.toggle()
        player.fullscreen.click()
        active = player.expanded
        QTest.qWait(160)
        QTest.keyClick(active, key)
        QTest.qWait(160)
        report["checks"]["key_exit_" + str(index)] = player.expanded is None and player.media.videoOutput() is player.video and player.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        player.media.pause()
    for index in range(4):
        player.fullscreen.click()
        QTest.qWait(100)
        player.expanded.close()
        QTest.qWait(100)
    report["checks"]["repeated_open_and_close"] = player.expanded is None and player.media.videoOutput() is player.video and not player.video.isFullScreen()
    player.fullscreen.click()
    QTest.qWait(120)
    QTest.mouseDClick(player.expanded.poster, Qt.MouseButton.LeftButton)
    QTest.qWait(120)
    report["checks"]["double_click_exit"] = player.expanded is None
    player.fullscreen.click()
    expanded = player.expanded
    player.load(str(Path(sys.argv[3]).resolve()))
    wait_until(lambda: not player.priming and 0 < player.duration < 5)
    QTest.qWait(200)
    report["checks"]["switch_video_inside_expanded"] = expanded.slider.maximum() == 4000 and not expanded.poster.pixmap().isNull() and player.start == 0 and player.media.videoOutput() is expanded.video
    player.close_player()
    QTest.qWait(100)
    report["checks"]["close_cleans_up_expanded"] = player.expanded is None
    report["ok"] = all(report["checks"].values())
finally:
    window.close()
    app.processEvents()
    atomic_json(root / "expanded-report.json", report)
assert report["ok"], report
print("Expanded playback, seek, sound, exits, repeated entry and video switching passed.")
