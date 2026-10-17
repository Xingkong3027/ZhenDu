from pathlib import Path

from PySide6.QtCore import QEvent, QSignalBlocker, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QKeySequence, QPixmap, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer, QVideoFrame
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import QCheckBox, QDialog, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSlider, QStackedWidget, QVBoxLayout, QWidget

from .config import time_text
from .language import t


class ExpandedPreview(QDialog):
    """A normal full-screen window with controls and its own video surface."""
    def __init__(self, player):
        super().__init__(player.window())
        self.player = player
        self.setModal(False)
        self.setWindowIcon(player.window().windowIcon())
        self.setStyleSheet(player.window().styleSheet())
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.bindings = []
        self._poster_key = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(10)
        self.surface = QStackedWidget()
        self.surface.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.video = QVideoWidget()
        self.video.setAspectRatioMode(Qt.AspectRatioMode.KeepAspectRatio)
        self.video.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.poster = QLabel()
        self.poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.poster.setStyleSheet("background: #08121b;")
        self.surface.addWidget(self.video)
        self.surface.addWidget(self.poster)
        self.surface.setCurrentWidget(self.poster)
        layout.addWidget(self.surface, 1)
        self.message = QLabel()
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.message)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.sliderPressed.connect(player.drag_start)
        self.slider.sliderMoved.connect(player.drag_move)
        self.slider.sliderReleased.connect(lambda: player.drag_end(self.slider.value()))
        layout.addWidget(self.slider)
        controls = QHBoxLayout()
        self.play_button = self.button("播放", "Play", player.toggle)
        controls.addWidget(self.play_button)
        controls.addWidget(self.button("−0.1 秒", "−0.1 s", lambda: player.seek_step(-0.1)))
        controls.addWidget(self.button("+0.1 秒", "+0.1 s", lambda: player.seek_step(0.1)))
        self.time_label = QLabel()
        self.time_label.setObjectName("timecode")
        controls.addWidget(self.time_label)
        controls.addStretch()
        self.exit_button = self.button("退出放大 · Esc", "Exit expanded view · Esc", self.close)
        controls.addWidget(self.exit_button)
        layout.addLayout(controls)
        edits = QHBoxLayout()
        self.a_button = self.button("当前画面设为 A", "Set A here", lambda: player.mark_start.emit(player.media.position() / 1000))
        self.b_button = self.button("当前画面设为 B", "Set B here", lambda: player.mark_end.emit(player.media.position() / 1000))
        edits.addWidget(self.a_button)
        edits.addWidget(self.b_button)
        self.loop = QCheckBox()
        self.bindings.append((self.loop, "循环 A/B", "Loop A/B"))
        self.loop.toggled.connect(player.loop.setChecked)
        edits.addWidget(self.loop)
        self.range_label = QLabel()
        self.range_label.setObjectName("muted")
        edits.addWidget(self.range_label)
        edits.addStretch()
        self.mute = QCheckBox()
        self.bindings.append((self.mute, "静音", "Mute"))
        self.mute.toggled.connect(player.mute.setChecked)
        edits.addWidget(self.mute)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setMaximumWidth(140)
        self.volume.valueChanged.connect(player.volume.setValue)
        edits.addWidget(self.volume)
        layout.addLayout(edits)
        self.hint = QLabel()
        self.hint.setObjectName("muted")
        layout.addWidget(self.hint)
        for sequence, callback in (("Space", player.toggle), ("Left", lambda: player.seek_step(-0.1)),
                                   ("Right", lambda: player.seek_step(0.1)), ("Escape", self.close), ("F11", self.close)):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
        self.video.videoSink().videoFrameChanged.connect(player.frame_received)
        self.video.installEventFilter(self)
        self.poster.installEventFilter(self)
        self.surface.installEventFilter(self)
        self.retranslate()

    def button(self, chinese, english, callback):
        button = QPushButton()
        button.clicked.connect(callback)
        self.bindings.append((button, chinese, english))
        return button

    def retranslate(self):
        self.setWindowTitle(t("放大预览", "Expanded preview") + " · " + Path(self.player.path).name)
        for widget, chinese, english in self.bindings:
            widget.setText(t(chinese, english))
        self.hint.setText(t("空格：播放／暂停 · Esc / F11：返回 · 双击画面：返回", "Space: play / pause · Esc / F11: return · Double-click video: return"))
        self.sync()

    def sync(self):
        player = self.player
        playing = player.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self.play_button.setText(t("暂停", "Pause") if playing else t("播放", "Play"))
        self.slider.setRange(0, max(1, player.media.duration()))
        if not player.dragging:
            self.slider.setValue(player.media.position())
        display_position = player.pending_seek if player.dragging else player.media.position()
        self.time_label.setText(f"{time_text(display_position / 1000)} / {time_text(player.duration)}")
        self.range_label.setText(player.range_label.text())
        self.message.setText(player.message.text())
        for widget, value in ((self.mute, player.mute.isChecked()), (self.loop, player.loop.isChecked())):
            with QSignalBlocker(widget):
                widget.setChecked(value)
        with QSignalBlocker(self.volume):
            self.volume.setValue(player.volume.value())
        self.loop.setEnabled(player.loop.isEnabled())
        for widget in (self.slider, self.play_button):
            widget.setEnabled(player.play_button.isEnabled())
        self.a_button.setEnabled(player.a_button.isEnabled())
        self.b_button.setEnabled(player.b_button.isEnabled())
        if playing and not player.priming:
            self.surface.setCurrentWidget(self.video)
        elif not player.priming:
            self.show_poster()

    def show_poster(self):
        frame = self.player.frame_image
        if frame is not None and not frame.isNull():
            key = (frame.cacheKey(), self.surface.width(), self.surface.height())
            if key != self._poster_key:
                self.poster.setPixmap(QPixmap.fromImage(frame).scaled(self.surface.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                                                     Qt.TransformationMode.SmoothTransformation))
                self._poster_key = key
            self.surface.setCurrentWidget(self.poster)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.MouseButtonDblClick and event.button() == Qt.MouseButton.LeftButton:
            self.close()
            return True
        if watched is self.surface and event.type() == QEvent.Type.Resize and self.surface.currentWidget() is self.poster:
            self.show_poster()
        return super().eventFilter(watched, event)

    def done(self, result):
        self.player.release_expanded(self)
        super().done(result)
        self.deleteLater()


class Player(QWidget):
    mark_start = Signal(float)
    mark_end = Signal(float)
    error = Signal(str)
    loaded = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("player")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.media = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.media.setAudioOutput(self.audio)
        self.audio.setVolume(0.65)
        self.video = QVideoWidget(self)
        self.video.setMinimumSize(260, 180)
        self.video.setMaximumHeight(390)
        self.surface = QStackedWidget(self)
        self.surface.setMinimumSize(260, 180)
        self.surface.setMaximumHeight(300)
        self.poster = QLabel()
        self.poster.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.poster.setStyleSheet("background: #08121b; border-radius: 8px;")
        self.surface.addWidget(self.video)
        self.surface.addWidget(self.poster)
        self.surface.setCurrentWidget(self.poster)
        self.media.setVideoOutput(self.video)
        self.path = ""
        self.duration = 0.0
        self.start = 0.0
        self.end = 0.0
        self.priming = False
        self.want_play = False
        self.dragging = False
        self.resume_after_drag = False
        self.pending_seek = 0
        self.frame_image = None
        self.last_frame = None
        self.frame_count = 0
        self._loop_seeking = False
        self.bindings = []
        self.expanded = None
        self.editing_enabled = True
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(9)
        self.message = QLabel()
        self.message.setObjectName("playerMessage")
        self.message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message.setWordWrap(True)
        layout.addWidget(self.surface, 1)
        layout.addWidget(self.message)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1)
        layout.addWidget(self.slider)
        control = QHBoxLayout()
        self.play_button = self.button("播放", "Play", self.toggle)
        self.previous = self.button("−0.1 秒", "−0.1 s", lambda: self.seek_step(-0.1))
        self.next = self.button("+0.1 秒", "+0.1 s", lambda: self.seek_step(0.1))
        self.time_label = QLabel("00:00:00.000 / 00:00:00.000")
        self.time_label.setObjectName("timecode")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        for widget in (self.play_button, self.previous, self.next):
            control.addWidget(widget)
        control.addStretch()
        control.addWidget(self.time_label)
        layout.addLayout(control)
        marks = QHBoxLayout()
        self.a_button = self.button("当前画面设为 A", "Set A here", lambda: self.mark_start.emit(self.media.position() / 1000))
        self.b_button = self.button("当前画面设为 B", "Set B here", lambda: self.mark_end.emit(self.media.position() / 1000))
        self.loop = QCheckBox()
        self.bindings.append((self.loop, "循环 A/B", "Loop A/B"))
        marks.addWidget(self.a_button)
        marks.addWidget(self.b_button)
        marks.addWidget(self.loop)
        marks.addStretch()
        self.fullscreen = self.button("放大", "Expand", self.toggle_expanded)
        marks.addWidget(self.fullscreen)
        layout.addLayout(marks)
        sound = QHBoxLayout()
        self.mute = QCheckBox()
        self.bindings.append((self.mute, "静音", "Mute"))
        self.mute.toggled.connect(self.set_muted)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(65)
        self.volume.setMaximumWidth(130)
        self.volume.valueChanged.connect(lambda value: self.audio.setVolume(value / 100))
        self.range_label = QLabel()
        self.range_label.setObjectName("muted")
        sound.addWidget(self.mute)
        sound.addWidget(self.volume)
        sound.addStretch()
        sound.addWidget(self.range_label)
        layout.addLayout(sound)
        self.seek_timer = QTimer(self)
        self.seek_timer.setSingleShot(True)
        self.seek_timer.setInterval(100)
        self.seek_timer.timeout.connect(lambda: self.media.setPosition(self.pending_seek))
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(80)
        self.refresh_timer.timeout.connect(self.refresh_position)
        self.refresh_timer.start()
        self.slider.sliderPressed.connect(self.drag_start)
        self.slider.sliderMoved.connect(self.drag_move)
        self.slider.sliderReleased.connect(self.drag_end)
        self.media.durationChanged.connect(self.duration_changed)
        self.media.mediaStatusChanged.connect(self.status_changed)
        self.media.playbackStateChanged.connect(lambda _: self.update_play_text())
        self.media.errorOccurred.connect(self.failed)
        self.video.videoSink().videoFrameChanged.connect(self.frame_received)
        self.media.positionChanged.connect(self.check_loop)
        for sequence, callback in (("Space", self.toggle), ("Left", lambda: self.seek_step(-0.1)),
                                   ("Right", lambda: self.seek_step(0.1)), ("Escape", self.close_expanded), ("F11", self.toggle_expanded)):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(callback)
        self.set_enabled(False)
        self.retranslate()

    def button(self, chinese, english, callback):
        button = QPushButton()
        button.clicked.connect(callback)
        self.bindings.append((button, chinese, english))
        return button

    def retranslate(self):
        for widget, chinese, english in self.bindings:
            widget.setText(t(chinese, english))
        self.update_play_text()
        self.update_range(self.start, self.end)
        if self.expanded:
            self.expanded.retranslate()
        if not self.path:
            self.message.setText(t("选择视频开始预览 · 支持声音播放", "Select a video to preview · audio supported"))

    def set_enabled(self, enabled):
        for widget in (self.slider, self.play_button, self.previous, self.next, self.a_button, self.b_button, self.fullscreen):
            widget.setEnabled(enabled)
        self.a_button.setEnabled(enabled and self.editing_enabled)
        self.b_button.setEnabled(enabled and self.editing_enabled)

    def set_editing_enabled(self, enabled):
        self.editing_enabled = enabled
        self.set_enabled(self.play_button.isEnabled())

    def load(self, path):
        self.seek_timer.stop()
        self.media.stop()
        self.media.setSource(QUrl())
        self.path = str(path)
        self.duration = self.start = self.end = 0.0
        self.frame_image = None
        self.last_frame = None
        self.poster.clear()
        if self.expanded:
            self.expanded.poster.clear()
            self.expanded.surface.setCurrentWidget(self.expanded.poster)
        self.surface.setCurrentWidget(self.poster)
        self.frame_count = 0
        self.pending_seek = 0
        self.dragging = self._loop_seeking = False
        self.want_play = False
        self.priming = True
        self.audio.setMuted(True)
        self.slider.setValue(0)
        self.set_enabled(False)
        self.loop.setChecked(False)
        self.message.setText(t("正在加载预览…", "Loading preview…"))
        self.update_range(0, 0)
        self.media.setSource(QUrl.fromLocalFile(self.path))
        if self.expanded:
            self.expanded.retranslate()

    def clear(self):
        self.close_expanded()
        self.seek_timer.stop()
        self.media.stop()
        self.media.setSource(QUrl())
        self.path = ""
        self.last_frame = None
        self.frame_image = None
        self.poster.clear()
        self.surface.setCurrentWidget(self.poster)
        self.priming = False
        self.set_enabled(False)
        self.retranslate()

    def duration_changed(self, milliseconds):
        if milliseconds <= 0:
            return
        self.duration = milliseconds / 1000
        self.slider.setRange(0, max(1, milliseconds))
        self.end = self.duration if not self.end else min(self.end, self.duration)
        self.loaded.emit(self.duration)

    def status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.LoadedMedia and self.priming:
            self.media.setPosition(0)
            self.media.play()
        elif status == QMediaPlayer.MediaStatus.EndOfMedia and self.loop.isChecked() and self.end > self.start:
            self.media.setPosition(round(self.start * 1000))
            self.media.play()

    def frame_received(self, frame):
        if not frame.isValid() or not self.path:
            return
        self.frame_count += 1
        self.last_frame = QVideoFrame(frame)
        if self.priming:
            self.frame_image = frame.toImage()
            self.priming = False
            self.message.clear()
            self.set_enabled(True)
            if not self.want_play:
                self.media.pause()
            self.audio.setMuted(self.mute.isChecked())
            self.update_play_text()
        elif self.media.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
            self.frame_image = self.last_frame.toImage()
            self.show_poster()

    def failed(self, error, message):
        self.priming = False
        self.audio.setMuted(self.mute.isChecked())
        self.set_enabled(False)
        detail = t("预览失败：{message}", "Preview failed: {message}", message=message)
        self.message.setText(detail)
        self.error.emit(detail)

    def set_muted(self, muted):
        self.audio.setMuted(True if self.priming else muted)

    def toggle(self):
        if not self.path:
            return
        if self.priming:
            self.want_play = not self.want_play
        elif self.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media.pause()
        else:
            if self.media.position() >= self.media.duration() - 20:
                self.media.setPosition(round(self.start * 1000) if self.loop.isChecked() else 0)
            self.media.play()
        self.update_play_text()

    def update_play_text(self):
        playing = self.want_play if self.priming else self.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self.play_button.setText(t("暂停", "Pause") if playing else t("播放", "Play"))
        if playing and not self.priming:
            if self.expanded:
                self.expanded.surface.setCurrentWidget(self.expanded.video)
            else:
                self.surface.setCurrentWidget(self.video)
        elif not self.priming:
            if self.last_frame is not None:
                self.frame_image = self.last_frame.toImage()
            self.show_poster()
        if self.expanded:
            self.expanded.sync()

    def show_poster(self):
        if self.frame_image is not None and not self.frame_image.isNull():
            self.poster.setPixmap(QPixmap.fromImage(self.frame_image).scaled(self.surface.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                                                           Qt.TransformationMode.SmoothTransformation))
            self.surface.setCurrentWidget(self.poster)
        if self.expanded:
            self.expanded.show_poster()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.surface.currentWidget() is self.poster:
            self.show_poster()

    def refresh_position(self):
        position = self.media.position()
        if not self.dragging:
            self.slider.setValue(position)
        self.time_label.setText(f"{time_text((self.pending_seek if self.dragging else position) / 1000)} / {time_text(self.duration)}")
        if self.expanded:
            self.expanded.sync()

    def drag_start(self):
        self.dragging = True
        self.pending_seek = self.media.position()
        self.resume_after_drag = self.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        self.media.pause()

    def drag_move(self, value):
        self.pending_seek = min(value, max(0, self.media.duration() - 1))
        if not self.seek_timer.isActive():
            self.seek_timer.start()
        self.time_label.setText(f"{time_text(value / 1000)} / {time_text(self.duration)}")

    def drag_end(self, value=None):
        self.seek_timer.stop()
        self.media.setPosition(min(self.slider.value() if value is None else value, max(0, self.media.duration() - 1)))
        self.dragging = False
        if self.resume_after_drag:
            self.media.play()

    def seek_step(self, seconds):
        self.seek_timer.stop()
        self.media.pause()
        self.media.setPosition(min(max(0, self.media.position() + round(seconds * 1000)), max(0, self.media.duration() - 1)))

    def update_range(self, start, end):
        self.start, self.end = max(0.0, start), max(0.0, end)
        self.range_label.setText(f"A {time_text(self.start)}   B {time_text(self.end)}")
        self.loop.setEnabled(self.end > self.start)

    def check_loop(self, milliseconds):
        if milliseconds < self.end * 1000 - 50:
            self._loop_seeking = False
        if self.loop.isChecked() and self.end > self.start and self.media.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            if milliseconds >= self.end * 1000 - 15 and not self._loop_seeking:
                self._loop_seeking = True
                self.media.setPosition(round(self.start * 1000))

    def close_player(self):
        self.close_expanded()
        self.refresh_timer.stop()
        self.clear()

    def toggle_expanded(self):
        if self.expanded:
            self.close_expanded()
            return
        if not self.path or not self.play_button.isEnabled():
            return
        if self.last_frame is not None:
            self.frame_image = self.last_frame.toImage()
        self.surface.setCurrentWidget(self.poster)
        self.show_poster()
        self.expanded = ExpandedPreview(self)
        self.expanded.setGeometry(self.window().screen().geometry())
        self.expanded.showFullScreen()
        self.media.setVideoOutput(self.expanded.video)
        self.expanded.sync()
        self.expanded.setFocus()

    def close_expanded(self):
        if self.expanded:
            self.expanded.close()

    def release_expanded(self, dialog):
        if self.expanded is not dialog:
            return
        if self.dragging:
            self.drag_end(dialog.slider.value())
        if self.last_frame is not None:
            self.frame_image = self.last_frame.toImage()
        self.last_frame = None
        self.expanded = None
        self.media.setVideoOutput(self.video)
        self.show_poster()
        self.update_play_text()
        self.setFocus()
