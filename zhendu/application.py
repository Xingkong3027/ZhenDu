import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")

from PySide6.QtCore import QCoreApplication, QLockFile, QThread, QTimer, QUrl, qInstallMessageHandler
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox

from . import __version__
from .config import JobConfig, Store, atomic_json
from .language import UserError, language, system_language, t, translate_standard_widgets
from .media import probe
from .paths import app_root, config_root, media_binary, resource_path
from .shell import ShellIntegration
from .ui import MainWindow
from .window_theme import install_window_theme, title_bar_is_dark


class InstanceServer:
    PROTOCOL = 1

    def __init__(self, window, name):
        self.window = window
        self.server = QLocalServer(window)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.connections = {}
        QLocalServer.removeServer(name)
        if not self.server.listen(name):
            raise RuntimeError(self.server.errorString())
        self.server.newConnection.connect(self.accept)

    def accept(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            self.connections[socket] = bytearray()
            socket.readyRead.connect(lambda socket=socket: self.read(socket))
            socket.disconnected.connect(lambda socket=socket: self.remove(socket))
            if socket.bytesAvailable():
                self.read(socket)

    def read(self, socket):
        buffer = self.connections[socket]
        buffer.extend(bytes(socket.readAll()))
        if len(buffer) > 1024 * 1024:
            socket.abort()
            return
        while b"\n" in buffer:
            line, _, remainder = buffer.partition(b"\n")
            buffer[:] = remainder
            try:
                request = json.loads(line)
                if request.get("protocol") != self.PROTOCOL:
                    raise ValueError("Unsupported request version")
                handle_request(self.window, request)
                socket.write(b"OK\n")
                socket.flush()
            except Exception as error:
                self.window.append_log(str(error))
                socket.write(b"ERROR\n")
                socket.flush()

    def remove(self, socket):
        self.connections.pop(socket, None)
        socket.deleteLater()


def send_request(name, request, timeout=1200):
    socket = QLocalSocket()
    socket.connectToServer(name)
    if not socket.waitForConnected(timeout):
        return False
    socket.write(json.dumps(request, ensure_ascii=False).encode("utf-8") + b"\n")
    socket.flush()
    if socket.bytesToWrite() and not socket.waitForBytesWritten(2000):
        return False
    if not socket.bytesAvailable() and not socket.waitForReadyRead(4000):
        return False
    accepted = bytes(socket.readLine()).strip() == b"OK"
    socket.disconnectFromServer()
    return accepted


def handle_request(window, request):
    paths = [str(Path(path).resolve()) for path in request.get("files", []) if Path(path).is_file()]
    window.add_files(paths)
    window.showNormal()
    window.raise_()
    window.activateWindow()
    identifier = request.get("preset")
    if identifier:
        preset = window.store.get_preset(identifier)
        if not preset:
            QMessageBox.warning(window, t("预设不可用", "Preset unavailable"), t("该预设已删除，请重新选择。", "This preset was deleted. Select another preset."))
            return
        # A context-menu job always starts from clean defaults, never old A/B.
        config = JobConfig.from_dict(preset["settings"])
        window.apply_config(config)
        index = window.preset_combo.findData(identifier)
        if index >= 0:
            window.preset_combo.setCurrentIndex(index)
        if request.get("run") and paths:
            window.enqueue(paths, config)
    if request.get("manage"):
        window.manage_presets()


def diagnostics(app, window, filename, videos, test_expanded=False):
    """Exercise the actual packaged UI and multimedia plugin without a Python install."""
    report = {"version": __version__, "frozen": bool(getattr(sys, "frozen", False)), "checks": {}, "videos": []}
    report["checks"]["ffmpeg"] = Path(media_binary("ffmpeg.exe")).is_file()
    report["checks"]["ffprobe"] = Path(media_binary("ffprobe.exe")).is_file()
    report["checks"]["icon"] = not window.windowIcon().isNull()
    report["checks"]["language_simplified"] = system_language(0x0804) == "zh_CN"
    report["checks"]["language_traditional"] = system_language(0x0404) == "zh_CN"
    report["checks"]["language_english"] = system_language(0x0409) == "en"
    report["checks"]["language_japanese"] = system_language(0x0411) == "en"
    from PySide6.QtMultimedia import QAudioBufferOutput, QMediaDevices
    observer = QAudioBufferOutput(window)
    window.player.media.setAudioBufferOutput(observer)
    observer.audioBufferReceived.connect(lambda buffer: state.update(audio_buffers=state.get("audio_buffers", 0) + (1 if buffer.isValid() else 0)))
    report["audio_device_available"] = not QMediaDevices.defaultAudioOutput().isNull()
    window.player.audio.setVolume(0.15)
    window.show()
    state = {"index": 0, "ticks": 0, "entry": None, "playing": False, "audio_buffers": 0}

    def finish():
        window.player.media.pause()
        old = language.selection
        language.selection = "en"
        window.retranslate()
        report["checks"]["english_ui"] = window.start_button.text() == "Start processing"
        language.selection = "zh_CN"
        window.retranslate()
        app.processEvents()
        report["checks"]["chinese_ui"] = window.start_button.text() == "开始处理"
        report["checks"]["no_tkinter"] = "tkinter" not in sys.modules and "customtkinter" not in sys.modules
        report["checks"]["dark_main_title_bar"] = title_bar_is_dark(window)
        from .ui import SettingsDialog, PresetManager
        for name, dialog in (("settings", SettingsDialog(window.store, window.shell, window)),
                             ("presets", PresetManager(window.store, window.shell, window))):
            dialog.show()
            app.processEvents()
            report["checks"]["dark_" + name + "_title_bar"] = title_bar_is_dark(dialog)
            dialog.close()
        window.activateWindow()
        app.processEvents()
        screenshot = Path(filename).with_suffix(".png")
        window.grab().save(str(screenshot))
        rect = window.frameGeometry()
        window.screen().grabWindow(0, rect.x(), rect.y(), rect.width(), rect.height()).save(str(Path(filename).with_name(Path(filename).stem + "-full-window.png")))
        language.selection = "en"
        window.retranslate()
        app.processEvents()
        window.grab().save(str(Path(filename).with_name(Path(filename).stem + "-english.png")))
        language.selection = old
        report["ok"] = all(report["checks"].values()) and all(entry.get("frames", 0) > 5 and entry.get("probe_ok") and entry.get("range_reset") and entry.get("paused_seek")
                           and (not entry.get("has_audio") or entry.get("audio_buffers", 0) > 0 and not entry.get("audio_muted")) for entry in report["videos"])
        atomic_json(filename, report)
        window.close()
        app.exit(0 if report["ok"] else 1)

    def next_video():
        if state["index"] >= len(videos):
            if test_expanded and videos:
                QTimer.singleShot(300, lambda: expanded_diagnostics(window, filename, report, finish))
            else:
                QTimer.singleShot(300, finish)
            return
        path = str(Path(videos[state["index"]]).resolve())
        window.add_files([path])
        window.file_tree.setCurrentItem(window.files[path])
        state["entry"] = {"path": path, "probe_ok": False}
        state["ticks"] = 0
        state["playing"] = False
        state["audio_buffers"] = 0
        timer.start()

    def tick():
        state["ticks"] += 1
        entry = state["entry"]
        if state.get("checking_seek"):
            if state["ticks"] < 21:
                return
            timer.stop()
            frame = window.player.frame_image
            entry["paused_seek"] = bool(frame is not None and not frame.isNull() and window.player.frame_count > state["before_seek_frames"]
                                         and window.player.surface.currentWidget() is window.player.poster)
            if frame is not None:
                frame.save(str(Path(filename).with_name(f"preview-{state['index'] + 1}.png")))
            report["videos"].append(entry)
            state["checking_seek"] = False
            state["index"] += 1
            if state["index"] < len(videos):
                window.clip.setChecked(True)
                window.clip_start.setText("00:00:12.000")
            next_video()
            return
        if window.player.frame_count > 0 and state["ticks"] >= 4 and not state["playing"]:
            window.player.toggle()
            state["playing"] = True
        if state["ticks"] >= 16 and window.player.frame_count > 0 or state["ticks"] >= 80:
            entry.update(frames=window.player.frame_count, has_audio=window.player.media.hasAudio(),
                         audio_output_attached=window.player.media.audioOutput() is window.player.audio,
                         audio_muted=window.player.audio.isMuted(), audio_buffers=state["audio_buffers"],
                         position_ms=window.player.media.position(), range_reset=window.clip_start.text() == "00:00:00.000",
                         probe_ok=entry["path"] in window.media_infos,
                         media_error=window.player.media.errorString())
            window.player.media.pause()
            state["before_seek_frames"] = window.player.frame_count
            state["checking_seek"] = True
            window.player.media.setPosition(750)

    timer = QTimer(window)
    timer.setInterval(200)
    timer.timeout.connect(tick)
    QTimer.singleShot(100, next_video)


def expanded_diagnostics(window, filename, report, finish):
    """Check the compiled preview host, rendering layout and real controls."""
    from PySide6.QtMultimedia import QMediaPlayer
    player = window.player
    checks = report["checks"]
    screen_size = window.screen().geometry().size()
    source = player.media.source()
    old_volume, old_mute = player.volume.value(), player.mute.isChecked()
    player.media.pause()
    player.fullscreen.click()
    dialog = player.expanded
    if dialog is None:
        checks["expanded_opens"] = False
        finish()
        return

    def opened():
        checks["expanded_opens"] = dialog.isFullScreen() and not dialog.video.isFullScreen()
        checks["expanded_controls_visible"] = all(widget.isVisible() for widget in (dialog.slider, dialog.time_label, dialog.play_button, dialog.exit_button, dialog.volume))
        checks["expanded_paused_layout"] = dialog.surface.height() > 400 and dialog.poster.geometry() == dialog.surface.rect() and not dialog.poster.pixmap().isNull()
        checks["expanded_resolution_unchanged"] = window.screen().geometry().size() == screen_size
        state["frames"] = player.frame_count
        dialog.play_button.click()
        QTimer.singleShot(600, played)

    def played():
        checks["expanded_plays"] = player.frame_count > state["frames"] + 5 and player.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        checks["expanded_playing_layout"] = dialog.video.geometry() == dialog.surface.rect()
        dialog.play_button.click()
        state["target"] = min(1250, max(0, player.media.duration() - 200))
        dialog.slider.sliderPressed.emit()
        dialog.slider.setValue(state["target"])
        dialog.slider.sliderMoved.emit(state["target"])
        dialog.slider.sliderReleased.emit()
        QTimer.singleShot(300, sought)

    def sought():
        checks["expanded_seek_and_time"] = abs(player.media.position() - state["target"]) < 150 and time_text(state["target"] / 1000) in dialog.time_label.text()
        dialog.volume.setValue(37)
        dialog.mute.setChecked(True)
        checks["expanded_sound_controls"] = player.audio.isMuted() and abs(player.audio.volume() - 0.37) < 0.001
        dialog.mute.setChecked(old_mute)
        dialog.volume.setValue(old_volume)
        dialog.grab().save(str(Path(filename).with_name(Path(filename).stem + "-expanded.png")))
        dialog.exit_button.click()
        QTimer.singleShot(250, returned)

    def returned():
        checks["expanded_exit_restores_preview"] = player.expanded is None and player.media.videoOutput() is player.video and abs(player.media.position() - state["target"]) < 150
        player.toggle()
        player.fullscreen.click()
        state["frames"] = player.frame_count
        QTimer.singleShot(350, repeated)

    def repeated():
        checks["expanded_repeated_playback"] = player.frame_count > state["frames"] + 3 and player.media.source() == source
        player.close_expanded()
        checks["expanded_preserves_playback"] = player.expanded is None and player.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        player.media.pause()
        QTimer.singleShot(150, finish)

    from .config import time_text
    state = {}
    QTimer.singleShot(250, opened)


def main(argv=None):
    parser = argparse.ArgumentParser(description="ZhenDu Video Tools")
    parser.add_argument("files", nargs="*")
    parser.add_argument("--preset")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--manage-presets", action="store_true")
    parser.add_argument("--register-shell", action="store_true")
    parser.add_argument("--unregister-shell", action="store_true")
    parser.add_argument("--self-test", metavar="REPORT")
    parser.add_argument("--test-video", action="append", default=[])
    parser.add_argument("--test-expanded", action="store_true")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("ZhenDu")
    app.setOrganizationName("ZhenDu")
    install_window_theme(app)
    try:
        store = Store()
        store.root.mkdir(parents=True, exist_ok=True)
        language.selection = store.data["language"]
        translate_standard_widgets()
        log_path = store.root / "application.log"

        def log_message(kind, context, message):
            try:
                if log_path.exists() and log_path.stat().st_size > 2 * 1024**2:
                    log_path.replace(store.root / "application.previous.log")
                with log_path.open("a", encoding="utf-8") as handle:
                    handle.write(str(message) + "\n")
            except OSError:
                pass

        qInstallMessageHandler(log_message)

        def exception_hook(error_type, value, trace):
            detail = "".join(traceback.format_exception(error_type, value, trace))
            log_message(None, None, detail)
            QMessageBox.critical(None, t("发生错误", "An error occurred"), str(value))

        sys.excepthook = exception_hook
        shell = ShellIntegration(store)
        if args.register_shell:
            shell.register()
            return 0
        if args.unregister_shell:
            shell.unregister()
            return 0
        for name in ("ffmpeg.exe", "ffprobe.exe"):
            media_binary(name)
        request = {"protocol": InstanceServer.PROTOCOL, "files": args.files, "preset": args.preset,
                   "run": args.run, "manage": args.manage_presets}
        instance_key = hashlib.sha256((str(app_root()).casefold() + str(store.root).casefold()).encode("utf-8")).hexdigest()[:24]
        name = "ZhenDu-" + instance_key
        lock = None
        if not args.self_test:
            if send_request(name, request, 200):
                return 0
            lock = QLockFile(str(store.root / (instance_key + ".lock")))
            lock.setStaleLockTime(0)
            if not lock.tryLock(100):
                # A concurrent launch can see the lock before the UI/server is ready.
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    if send_request(name, request, 200):
                        return 0
                    QThread.msleep(80)
                raise UserError("另一实例正在启动，请稍后重试。", "Another instance is starting. Please try again shortly.")
        window = MainWindow(store, shell)
        if args.self_test:
            diagnostics(app, window, args.self_test, args.test_video, args.test_expanded)
        else:
            server = InstanceServer(window, name)
            window.show()
            QTimer.singleShot(0, lambda: handle_request(window, request))
        result = app.exec()
        if lock:
            lock.unlock()
        return result
    except Exception as error:
        if args.self_test:
            atomic_json(args.self_test, {"ok": False, "error": str(error), "traceback": traceback.format_exc()})
        else:
            QMessageBox.critical(None, t("帧渡启动失败", "ZhenDu could not start"), error.localized() if isinstance(error, UserError) else str(error))
        return 1
