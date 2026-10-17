from dataclasses import asdict
import json
from pathlib import Path
import queue
import uuid

from PySide6.QtCore import QMimeData, QSignalBlocker, Qt, QThreadPool, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                              QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView,
                              QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
                              QMenu, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSpinBox,
                              QSplitter, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from . import __version__
from .config import JobConfig, Store, atomic_json, parse_time, time_text
from .language import UserError, language, t, translate_standard_widgets
from .media import ProbeCache
from .paths import resource_path
from .player import Player
from .shell import ShellIntegration
from .workers import ProbeTask, Task, TaskWorker


STYLE = """
QWidget { color: #e5edf4; font-family: 'Segoe UI', 'Microsoft YaHei UI'; font-size: 13px; }
QMainWindow, QDialog { background: #10171f; }
QLabel { background: transparent; }
QLabel#brand { font-size: 27px; font-weight: 700; color: #63dfc5; }
QLabel#muted, QLabel#playerMessage { color: #91a4b6; }
QLabel#timecode { color: #bdcede; font-family: Consolas; font-size: 12px; }
QLabel#section { font-size: 15px; font-weight: 600; }
QGroupBox { background: #18222d; border: 1px solid #2a3745; border-radius: 10px; margin-top: 9px; padding-top: 14px; }
QGroupBox::title { subcontrol-origin: margin; left: 13px; padding: 0 5px; color: #bdcede; }
QPushButton { background: #23313f; border: 1px solid #33475a; border-radius: 6px; padding: 7px 10px; }
QPushButton:hover { background: #304357; border-color: #608096; }
QPushButton:pressed { background: #1a2733; }
QPushButton:disabled { color: #657687; border-color: #27333f; background: #1b2631; }
QPushButton#primary { background: #51d7b8; color: #09251f; border: none; font-weight: 700; padding: 10px 18px; }
QPushButton#primary:hover { background: #7ee9ce; }
QPushButton#danger { color: #ffb0a2; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background: #111c26; border: 1px solid #334252; border-radius: 5px; padding: 6px; min-height: 19px; }
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus { border-color: #51d7b8; }
QComboBox QAbstractItemView { background: #20303e; selection-background-color: #2d695c; }
QTreeWidget, QListWidget, QPlainTextEdit { background: #141e28; border: 1px solid #2a3745; border-radius: 7px; alternate-background-color: #182532; }
QTreeWidget::item, QListWidget::item { padding: 7px 5px; }
QTreeWidget::item:selected, QListWidget::item:selected { background: #24594f; color: white; }
QHeaderView::section { background: #1f2d3a; color: #a9bdcf; border: none; padding: 6px; }
QTabWidget::pane { background: #18222d; border: 1px solid #2a3745; border-radius: 8px; }
QTabBar::tab { background: #192633; padding: 10px 13px; color: #9fb3c5; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #70e3c8; border-bottom-color: #51d7b8; }
QScrollArea { border: none; background: transparent; }
QWidget#tabBody { background: #18222d; }
QLabel:disabled, QCheckBox:disabled { color: #718496; }
QScrollBar:vertical { background: #17232e; width: 8px; margin: 0; }
QScrollBar::handle:vertical { background: #41556a; border-radius: 4px; min-height: 25px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QProgressBar { border: none; background: #233442; border-radius: 4px; height: 9px; text-align: center; }
QProgressBar::chunk { background: #51d7b8; border-radius: 4px; }
QSlider::groove:horizontal { height: 5px; background: #324354; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #51d7b8; border-radius: 2px; }
QSlider::handle:horizontal { width: 13px; margin: -5px 0; border-radius: 6px; background: #81ecd2; }
QCheckBox { spacing: 7px; }
QCheckBox::indicator { width: 15px; height: 15px; border: 1px solid #577084; border-radius: 3px; background: #12202b; }
QCheckBox::indicator:checked { background: #51d7b8; border-color: #51d7b8; }
QSplitter::handle { background: #10171f; width: 7px; height: 7px; }
QToolTip { background: #243746; color: #e5edf4; border: 1px solid #4b6379; padding: 6px; }
"""


def error_message(parent, error):
    text = error.localized() if isinstance(error, UserError) else str(error)
    QMessageBox.warning(parent, t("帧渡", "ZhenDu"), text)


class SettingsDialog(QDialog):
    changed = Signal()

    def __init__(self, store, shell, parent=None):
        super().__init__(parent)
        self.store, self.shell = store, shell
        self.setWindowTitle(t("设置", "Settings"))
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.language_combo = QComboBox()
        self.language_combo.addItem(language.automatic_label(), "auto")
        self.language_combo.addItem("简体中文", "zh_CN")
        self.language_combo.addItem("English", "en")
        self.language_combo.setCurrentIndex(self.language_combo.findData(store.data["language"]))
        form.addRow(t("界面语言", "Interface language"), self.language_combo)
        layout.addLayout(form)
        note = QLabel(t("自动模式：简体／繁体中文系统使用简体中文，其他系统使用 English。",
                        "Automatic: Simplified or Traditional Chinese systems use Simplified Chinese; other systems use English."))
        note.setWordWrap(True)
        note.setObjectName("muted")
        layout.addWidget(note)
        output_group = QGroupBox(t("输出方式", "Output layout"))
        output_layout = QVBoxLayout(output_group)
        self.task_subfolders = QCheckBox(t("为每个任务创建子文件夹", "Create a subfolder for each task"))
        self.task_subfolders.setChecked(store.data.get("task_subfolders", False))
        output_layout.addWidget(self.task_subfolders)
        output_note = QLabel(t("默认关闭：视频直接保存在输出目录；未选择目录时保存在原视频旁。开启后使用原来的独立任务文件夹。重名时自动编号，不覆盖源文件。",
                               "Off by default: save videos directly in the output folder, or beside the source if no folder is selected. Enable to keep separate task folders. Existing files are never overwritten."))
        output_note.setWordWrap(True)
        output_note.setObjectName("muted")
        output_layout.addWidget(output_note)
        layout.addWidget(output_group)
        group = QGroupBox(t("资源管理器右键菜单", "File Explorer context menu"))
        group_layout = QVBoxLayout(group)
        self.shell_status = QLabel()
        self.shell_status.setWordWrap(True)
        group_layout.addWidget(self.shell_status)
        row = QHBoxLayout()
        register = QPushButton(t("注册／修复菜单", "Register / repair menu"))
        unregister = QPushButton(t("撤销右键菜单", "Remove context menu"))
        unregister.setObjectName("danger")
        register.clicked.connect(self.register_menu)
        unregister.clicked.connect(self.unregister_menu)
        row.addWidget(register)
        row.addWidget(unregister)
        group_layout.addLayout(row)
        details = QLabel(t("只为当前用户添加视频菜单。移动程序后可重新注册；Windows 11 中通过“显示更多选项”访问。",
                           "Adds video commands for the current user. Register again after moving the app. On Windows 11, use Show more options."))
        details.setWordWrap(True)
        details.setObjectName("muted")
        group_layout.addWidget(details)
        layout.addWidget(group)
        config_note = QLabel(t("预设与设置位置：{path}", "Presets and settings: {path}", path=str(store.root)))
        config_note.setWordWrap(True)
        config_note.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(config_note)
        buttons = QDialogButtonBox()
        apply = buttons.addButton(t("应用并关闭", "Apply and close"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(t("取消", "Cancel"), QDialogButtonBox.ButtonRole.RejectRole)
        apply.clicked.connect(self.apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.refresh_status()

    def refresh_status(self):
        owner = self.shell.owner()
        self.shell_status.setText(t("尚未注册。", "Not registered.") if not owner else
                                 t("当前菜单指向：{path}", "Current menu points to: {path}", path=self.shell.registered_path()))

    def register_menu(self):
        try:
            self.shell.register()
            self.refresh_status()
        except Exception as error:
            error_message(self, error)

    def unregister_menu(self):
        try:
            force = False
            if self.shell.owner() and not self.shell.owns_menu():
                answer = QMessageBox.question(self, t("撤销菜单", "Remove menu"),
                                              t("菜单由另一份程序注册：{path}\n是否撤销这份菜单？", "The menu belongs to another copy: {path}\nRemove that menu?", path=self.shell.registered_path()))
                if answer != QMessageBox.StandardButton.Yes:
                    return
                force = True
            self.shell.unregister(force)
            self.refresh_status()
        except Exception as error:
            error_message(self, error)

    def apply(self):
        try:
            self.store.data["language"] = self.language_combo.currentData()
            self.store.data["task_subfolders"] = self.task_subfolders.isChecked()
            self.store.save()
            language.selection = self.store.data["language"]
            self.shell.refresh_if_owned()
            self.changed.emit()
            self.accept()
        except Exception as error:
            error_message(self, error)


class SavePresetDialog(QDialog):
    def __init__(self, store, config, current_id=None, parent=None):
        super().__init__(parent)
        self.store, self.config, self.current_id = store, config, current_id
        self.setWindowTitle(t("保存预设", "Save preset"))
        layout = QVBoxLayout(self)
        self.name = QLineEdit()
        self.name.setPlaceholderText(t("例如：上传用 1080p", "For example: 1080p upload"))
        preset = store.get_preset(current_id)
        if preset:
            self.name.setText(store.preset_name(preset))
        layout.addWidget(QLabel(t("预设名称", "Preset name")))
        layout.addWidget(self.name)
        self.context = QCheckBox(t("显示在资源管理器右键菜单", "Show in File Explorer context menu"))
        self.context.setChecked(True)
        self.task = QCheckBox(t("同时保存分割规则", "Include split settings"))
        self.task.setChecked(config.split)
        self.clip = QCheckBox(t("同时保存固定 A/B 时间（用于相同时长素材）", "Include fixed A/B times (for matching source durations)"))
        self.overwrite = QCheckBox(t("更新当前预设", "Update the current preset"))
        self.overwrite.setEnabled(bool(preset))
        for widget in (self.context, self.task, self.clip, self.overwrite):
            layout.addWidget(widget)
        buttons = QDialogButtonBox()
        save = buttons.addButton(t("保存", "Save"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(t("取消", "Cancel"), QDialogButtonBox.ButtonRole.RejectRole)
        save.clicked.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save(self):
        try:
            self.store.save_preset(self.name.text(), self.config, self.context.isChecked(), self.task.isChecked(),
                                   self.clip.isChecked(), self.current_id if self.overwrite.isChecked() else None)
            self.accept()
        except Exception as error:
            error_message(self, error)


class PresetManager(QDialog):
    chosen = Signal(str)

    def __init__(self, store, shell, parent=None):
        super().__init__(parent)
        self.store, self.shell = store, shell
        self.setWindowTitle(t("管理预设", "Manage presets"))
        self.resize(620, 430)
        layout = QVBoxLayout(self)
        help_label = QLabel(t("勾选的预设显示在右键菜单中；上下移动可调整菜单顺序。", "Checked presets appear in the context menu. Move them up or down to change the order."))
        help_label.setWordWrap(True)
        layout.addWidget(help_label)
        self.list = QListWidget()
        layout.addWidget(self.list)
        self.refresh()
        self.list.itemChanged.connect(self.toggle_context)
        row = QHBoxLayout()
        for chinese, english, callback in (("应用", "Apply", self.choose), ("重命名", "Rename", self.rename),
                                           ("删除", "Delete", self.delete), ("↑", "↑", lambda: self.move(-1)),
                                           ("↓", "↓", lambda: self.move(1))):
            button = QPushButton(t(chinese, english))
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        row = QHBoxLayout()
        for chinese, english, callback in (("导入…", "Import…", self.import_presets), ("导出…", "Export…", self.export_presets),
                                           ("关闭", "Close", self.accept)):
            button = QPushButton(t(chinese, english))
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)

    def refresh(self):
        with QSignalBlocker(self.list):
            self.list.clear()
            for preset in self.store.presets:
                item = QListWidgetItem(self.store.preset_name(preset))
                item.setData(Qt.ItemDataRole.UserRole, preset["id"])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if preset.get("context") else Qt.CheckState.Unchecked)
                self.list.addItem(item)

    def commit(self):
        self.store.save()
        self.shell.refresh_if_owned()
        self.refresh()

    def current(self):
        item = self.list.currentItem()
        return self.store.get_preset(item.data(Qt.ItemDataRole.UserRole)) if item else None

    def choose(self):
        if preset := self.current():
            self.chosen.emit(preset["id"])
            self.accept()

    def toggle_context(self, item):
        try:
            self.store.get_preset(item.data(Qt.ItemDataRole.UserRole))["context"] = item.checkState() == Qt.CheckState.Checked
            self.store.save()
            self.shell.refresh_if_owned()
        except Exception as error:
            error_message(self, error)

    def rename(self):
        if preset := self.current():
            name, accepted = QInputDialog.getText(self, t("重命名", "Rename"), t("预设名称", "Preset name"), text=self.store.preset_name(preset))
            if accepted and name.strip():
                preset["name"] = name.strip()[:80]
                self.commit()

    def delete(self):
        if preset := self.current():
            if QMessageBox.question(self, t("删除预设", "Delete preset"), t("删除“{name}”？", "Delete “{name}”?", name=self.store.preset_name(preset))) == QMessageBox.StandardButton.Yes:
                self.store.data["presets"] = [item for item in self.store.presets if item["id"] != preset["id"]]
                self.commit()

    def move(self, delta):
        row = self.list.currentRow()
        target = row + delta
        if row >= 0 and 0 <= target < len(self.store.presets):
            self.store.presets[row], self.store.presets[target] = self.store.presets[target], self.store.presets[row]
            self.commit()
            self.list.setCurrentRow(target)

    def import_presets(self):
        filename, _ = QFileDialog.getOpenFileName(self, t("导入预设", "Import presets"), "", "JSON (*.json)")
        if not filename:
            return
        try:
            data = json.loads(Path(filename).read_text(encoding="utf-8"))
            if data.get("schema_version") != 1 or not isinstance(data.get("presets"), list):
                raise ValueError(t("不支持的预设文件。", "Unsupported preset file."))
            imported = []
            for preset in data["presets"]:
                Store.validate_preset(preset)
                value = dict(preset)
                value["id"] = uuid.uuid4().hex
                imported.append(value)
            self.store.data["presets"].extend(imported)
            self.commit()
        except Exception as error:
            error_message(self, error)

    def export_presets(self):
        filename, _ = QFileDialog.getSaveFileName(self, t("导出预设", "Export presets"), "zhendu-presets.json", "JSON (*.json)")
        if filename:
            try:
                atomic_json(filename, {"schema_version": 1, "presets": self.store.presets})
            except Exception as error:
                error_message(self, error)


class MainWindow(QMainWindow):
    def __init__(self, store, shell=None):
        super().__init__()
        self.store = store
        self.shell = shell or ShellIntegration(store)
        self.cache = ProbeCache()
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(2)
        self.probes = {}
        self.files = {}
        self.media_infos = {}
        self.jobs = {}
        self.task_queue = queue.Queue()
        self.worker = None
        self.current_path = ""
        self.previewing_result = False
        self._source_preview_path = ""
        self.bindings = []
        self.combos = []
        self.tab_titles = []
        self.setAcceptDrops(True)
        self.setWindowIcon(QIcon(str(resource_path("assets/zhendu.ico"))))
        available = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1360, available.width() - 50), min(820, available.height() - 50))
        self.setMinimumSize(980, 610)
        self.setStyleSheet(STYLE)
        self.build_ui()
        try:
            self.apply_config(JobConfig.from_dict(store.data.get("last_config", {})))
        except (ValueError, TypeError, UserError):
            self.apply_config(JobConfig())
        self.retranslate()
        if store.load_warning:
            self.append_log(t("设置文件已备份并恢复默认值：{error}", "Settings were backed up and reset: {error}", error=store.load_warning))

    def bind(self, widget, chinese, english, method="setText"):
        self.bindings.append((widget, method, chinese, english))
        getattr(widget, method)(t(chinese, english))
        return widget

    def label(self, chinese, english, object_name=None):
        widget = self.bind(QLabel(), chinese, english)
        if object_name:
            widget.setObjectName(object_name)
        return widget

    def button(self, chinese, english, callback, object_name=None):
        widget = self.bind(QPushButton(), chinese, english)
        widget.clicked.connect(callback)
        if object_name:
            widget.setObjectName(object_name)
        return widget

    def check(self, chinese, english):
        return self.bind(QCheckBox(), chinese, english)

    def combo(self, choices):
        widget = QComboBox()
        self.combos.append((widget, choices))
        for value, chinese, english in choices:
            widget.addItem(t(chinese, english), value)
        return widget

    def form_row(self, form, chinese, english, widget):
        form.addRow(self.label(chinese, english), widget)

    def tab(self, chinese, english):
        area = QScrollArea()
        area.setWidgetResizable(True)
        body = QWidget()
        body.setObjectName("tabBody")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(15, 18, 15, 15)
        layout.setSpacing(14)
        area.setWidget(body)
        index = self.tabs.addTab(area, t(chinese, english))
        self.tab_titles.append((index, chinese, english))
        return layout

    def build_ui(self):
        body = QWidget()
        self.setCentralWidget(body)
        root = QVBoxLayout(body)
        root.setContentsMargins(18, 14, 18, 16)
        root.setSpacing(12)
        header = QHBoxLayout()
        self.brand = self.label("帧渡", "ZhenDu", "brand")
        header.addWidget(self.brand)
        header.addWidget(self.label("视频压缩 · 截取 · 分割", "Compress · Trim · Split", "muted"))
        header.addStretch()
        header.addWidget(QLabel("v" + __version__))
        header.addWidget(self.button("设置", "Settings", self.open_settings))
        root.addLayout(header)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(self.splitter, 1)
        files_panel = QWidget()
        files_layout = QVBoxLayout(files_panel)
        files_layout.setContentsMargins(0, 0, 0, 0)
        files_layout.addWidget(self.label("素材列表", "Sources", "section"))
        self.file_tree = QTreeWidget()
        self.file_tree.setColumnCount(1)
        self.file_tree.setHeaderHidden(True)
        self.file_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_tree.setRootIsDecorated(False)
        self.file_tree.currentItemChanged.connect(self.select_preview)
        self.file_tree.itemClicked.connect(lambda item, _: self.select_preview(item, None))
        files_layout.addWidget(self.file_tree, 1)
        row = QHBoxLayout()
        row.addWidget(self.button("添加视频", "Add videos", self.add_dialog))
        row.addWidget(self.button("移除", "Remove", self.remove_files))
        files_layout.addLayout(row)
        help_label = self.label("可拖入多个视频。勾选要处理的素材，单击任意文件预览。", "Drop videos here. Check sources to process; click any file to preview.", "muted")
        help_label.setWordWrap(True)
        files_layout.addWidget(help_label)
        files_panel.setMinimumWidth(150)
        files_panel.setMaximumWidth(350)
        self.splitter.addWidget(files_panel)
        middle = QWidget()
        middle_layout = QVBoxLayout(middle)
        middle_layout.setContentsMargins(4, 0, 4, 0)
        middle_layout.setSpacing(10)
        self.source_title = self.label("预览", "Preview", "section")
        self.source_title.setWordWrap(True)
        middle_layout.addWidget(self.source_title)
        self.info_label = QLabel()
        self.info_label.setObjectName("muted")
        self.info_label.setWordWrap(True)
        middle_layout.addWidget(self.info_label)
        self.player = Player()
        self.player.video.setMaximumHeight(300)
        self.player.surface.setMaximumHeight(250)
        self.player.error.connect(self.append_log)
        self.player.mark_start.connect(self.set_a)
        self.player.mark_end.connect(self.set_b)
        self.player.loaded.connect(self.player_loaded)
        middle_layout.addWidget(self.player, 3)
        queue_header = QHBoxLayout()
        queue_header.addWidget(self.label("任务队列", "Tasks", "section"))
        queue_header.addStretch()
        queue_header.addWidget(self.button("重试失败任务", "Retry failed", self.retry_failed))
        queue_header.addWidget(self.button("打开输出", "Open output", self.open_output))
        middle_layout.addLayout(queue_header)
        self.task_tree = QTreeWidget()
        self.task_tree.setColumnCount(3)
        self.task_tree.setRootIsDecorated(True)
        self.task_tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.task_tree.setMinimumHeight(110)
        self.task_tree.setMaximumHeight(200)
        self.task_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.task_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.task_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.task_tree.itemDoubleClicked.connect(self.activate_result)
        self.task_tree.itemSelectionChanged.connect(self.refresh_result_actions)
        self.task_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.task_tree.customContextMenuRequested.connect(self.result_menu)
        shortcut = QShortcut(QKeySequence.StandardKey.Copy, self.task_tree)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self.copy_selected_results)
        middle_layout.addWidget(self.task_tree, 1)
        result_actions = QHBoxLayout()
        self.copy_result_button = self.button("复制文件", "Copy files", self.copy_selected_results)
        self.open_video_button = self.button("打开视频", "Open video", self.open_result)
        self.preview_result_button = self.button("预览", "Preview", self.preview_result)
        for button in (self.copy_result_button, self.open_video_button, self.preview_result_button):
            result_actions.addWidget(button)
        result_actions.addStretch()
        middle_layout.addLayout(result_actions)
        self.splitter.addWidget(middle)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.addWidget(self.label("处理设置", "Processing", "section"))
        row = QHBoxLayout()
        self.preset_combo = QComboBox()
        row.addWidget(self.preset_combo, 1)
        row.addWidget(self.button("应用", "Apply", self.apply_selected_preset))
        right_layout.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(self.button("保存为预设", "Save preset", self.save_preset))
        row.addWidget(self.button("管理", "Manage", self.manage_presets))
        right_layout.addLayout(row)
        self.tabs = QTabWidget()
        right_layout.addWidget(self.tabs, 1)
        right.setMinimumWidth(300)
        right.setMaximumWidth(430)
        self.splitter.addWidget(right)
        self.splitter.setSizes([210, 730, 350])
        self.splitter.setStretchFactor(1, 1)
        compression = self.tab("压缩", "Compress")
        self.compress = self.check("启用视频压缩", "Encode / compress video")
        compression.addWidget(self.compress)
        self.video_settings = QWidget()
        form = QFormLayout(self.video_settings)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(11)
        self.codec = self.combo([("h264", "H.264", "H.264"), ("hevc", "H.265", "H.265"), ("vp9", "VP9", "VP9"), ("av1", "AV1", "AV1")])
        self.backend = self.combo([("cpu", "软件 · CPU", "Software · CPU"), ("nvenc", "NVIDIA · NVENC", "NVIDIA · NVENC"),
                                   ("qsv", "Intel · QSV", "Intel · QSV"), ("amf", "AMD · AMF", "AMD · AMF")])
        self.speed = self.combo([(value, chinese, english) for value, chinese, english in
                                 (("ultrafast", "极快", "Ultra fast"), ("veryfast", "很快", "Very fast"), ("fast", "较快", "Fast"),
                                  ("medium", "中等", "Medium"), ("slow", "慢", "Slow"), ("veryslow", "很慢", "Very slow"))])
        self.quality = QSpinBox()
        self.quality.setRange(0, 63)
        self.quality.setValue(20)
        self.width, self.height = QSpinBox(), QSpinBox()
        for widget in (self.width, self.height):
            widget.setRange(0, 16384)
            widget.setSingleStep(2)
        self.fps = QDoubleSpinBox()
        self.fps.setRange(0, 240)
        self.fps.setDecimals(3)
        self.color = self.combo([("source", "保持原始", "Keep source"), ("limited", "有限范围", "Limited range"), ("full", "全范围", "Full range")])
        for chinese, english, widget in (("编码格式", "Codec", self.codec), ("编码设备", "Encoder", self.backend),
                                         ("速度", "Speed", self.speed), ("质量（越小越高）", "Quality (lower is better)", self.quality)):
            self.form_row(form, chinese, english, widget)
        compression.addWidget(self.video_settings)
        self.advanced = self.check("调整分辨率／帧率／色彩", "Resize / FPS / color")
        compression.addWidget(self.advanced)
        self.advanced_video = QWidget()
        advanced_form = QFormLayout(self.advanced_video)
        advanced_form.setContentsMargins(0, 0, 0, 0)
        for chinese, english, widget in (("目标宽度", "Target width", self.width), ("目标高度", "Target height", self.height),
                                         ("帧率", "Frame rate", self.fps), ("色彩范围", "Color range", self.color)):
            self.form_row(advanced_form, chinese, english, widget)
        compression.addWidget(self.advanced_video)
        self.zero_hint = self.label("宽高均为 0：保持原始；单边为 0：按比例自动。帧率 0：保持原始。", "Both dimensions 0: keep source. One dimension 0: preserve aspect ratio. FPS 0: keep source.", "muted")
        self.zero_hint.setWordWrap(True)
        compression.addWidget(self.zero_hint)
        audio_form = QFormLayout()
        self.audio_mode = self.combo([("copy", "直接复制（最快）", "Copy (fastest)"), ("encode", "转码音频", "Encode audio"), ("none", "移除音频", "Remove audio")])
        self.audio_bitrate = QSpinBox()
        self.audio_bitrate.setRange(8, 1536)
        self.audio_bitrate.setValue(128)
        self.audio_bitrate.setSuffix(" kbps")
        self.audio_track = QComboBox()
        self.audio_track.addItem(t("全部音轨", "All audio tracks"), -1)
        self.container = self.combo([("auto", "自动", "Auto"), ("mp4", "MP4", "MP4"), ("mkv", "MKV", "MKV"),
                                     ("webm", "WebM", "WebM"), ("mov", "MOV", "MOV"), ("ts", "TS", "TS")])
        for chinese, english, widget in (("音频处理", "Audio", self.audio_mode), ("音频码率", "Audio bitrate", self.audio_bitrate),
                                         ("音轨", "Audio tracks", self.audio_track), ("输出容器", "Container", self.container)):
            self.form_row(audio_form, chinese, english, widget)
        compression.addLayout(audio_form)
        self.subtitles = self.check("复制字幕（需容器兼容）", "Copy subtitles (container must support them)")
        compression.addWidget(self.subtitles)
        compression.addStretch()
        trim = self.tab("截取", "Trim")
        self.clip = self.check("启用截取片段", "Trim to A/B range")
        trim.addWidget(self.clip)
        trim_form = QFormLayout()
        self.clip_start = QLineEdit("00:00:00.000")
        self.clip_end = QLineEdit()
        self.bind(self.clip_end, "视频结尾", "End of video", "setPlaceholderText")
        self.form_row(trim_form, "起点 A", "Start A", self.clip_start)
        self.form_row(trim_form, "终点 B", "End B", self.clip_end)
        trim.addLayout(trim_form)
        trim.addWidget(self.button("重置为完整视频", "Reset to full video", self.reset_range))
        note = self.label("在预览中拖动时间轴，再用“设为 A/B”选择范围。可同时启用分割，按选中范围计算分段。", "Seek in the preview and set A/B. Splitting can be enabled together and uses the selected range.", "muted")
        note.setWordWrap(True)
        trim.addWidget(note)
        note = self.label("快速流复制截取受关键帧限制。需要精确边界时，请启用视频压缩／重编码。", "Fast stream-copy trimming is limited by keyframes. Enable video encoding when exact boundaries are required.", "muted")
        note.setWordWrap(True)
        trim.addWidget(note)
        trim.addStretch()
        split = self.tab("分割", "Split")
        self.split = self.check("启用分割片段", "Split into parts")
        split.addWidget(self.split)
        split_form = QFormLayout()
        self.split_mode = self.combo([("count", "按段数", "By part count"), ("duration", "按每段时长", "By duration"), ("size", "按每段大小", "By size")])
        self.split_count = QSpinBox()
        self.split_count.setRange(2, 1000)
        self.split_duration = QLineEdit("00:05:00")
        self.split_size = QDoubleSpinBox()
        self.split_size.setRange(1, 100000)
        self.split_size.setDecimals(2)
        self.split_size.setSuffix(" MiB")
        self.split_size.setValue(100)
        for chinese, english, widget in (("分割方式", "Split mode", self.split_mode), ("段数", "Part count", self.split_count),
                                         ("每段时长", "Part duration", self.split_duration), ("每段大小", "Part size", self.split_size)):
            self.form_row(split_form, chinese, english, widget)
        split.addLayout(split_form)
        self.size_safe = self.check("保守处理并验证不超过目标大小", "Conservative sizing; verify the limit")
        self.size_safe.setChecked(True)
        split.addWidget(self.size_safe)
        note = self.label("关闭视频压缩时直接复制视频流，优先速度与原始质量。时间和大小切点会受关键帧影响。", "With video encoding off, parts copy the video stream for speed and original quality. Keyframes affect time and size boundaries.", "muted")
        note.setWordWrap(True)
        split.addWidget(note)
        split.addStretch()
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setObjectName("muted")
        right_layout.addWidget(self.summary)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(1200)
        self.log_view.setMaximumHeight(135)
        self.log_view.hide()
        root.addWidget(self.log_view)
        output_row = QHBoxLayout()
        output_row.addWidget(self.label("输出位置", "Output"))
        self.output_dir = QLineEdit(self.store.data.get("output_dir", ""))
        self.bind(self.output_dir, "默认：原视频所在目录（可在设置中启用任务文件夹）", "Default: beside the source (task folders optional in Settings)", "setPlaceholderText")
        output_row.addWidget(self.output_dir, 1)
        output_row.addWidget(self.button("浏览…", "Browse…", self.browse_output))
        output_row.addWidget(self.button("日志", "Log", lambda: self.log_view.setVisible(not self.log_view.isVisible())))
        root.addLayout(output_row)
        footer = QHBoxLayout()
        progress_box = QVBoxLayout()
        self.progress_label = QLabel()
        self.progress_label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        progress_box.addWidget(self.progress_label)
        progress_box.addWidget(self.progress_bar)
        footer.addLayout(progress_box, 1)
        self.cancel_button = QPushButton()
        self.cancel_button.clicked.connect(self.task_footer_action)
        self.cancel_button.setEnabled(False)
        self.start_button = self.button("开始处理", "Start processing", self.start_processing, "primary")
        footer.addWidget(self.cancel_button)
        footer.addWidget(self.start_button)
        root.addLayout(footer)
        self.compress.toggled.connect(self.controls_changed)
        self.advanced.toggled.connect(self.controls_changed)
        self.clip.toggled.connect(self.controls_changed)
        self.split.toggled.connect(self.controls_changed)
        self.split_mode.currentIndexChanged.connect(self.controls_changed)
        self.audio_mode.currentIndexChanged.connect(self.controls_changed)
        self.clip_start.textChanged.connect(self.range_changed)
        self.clip_end.textChanged.connect(self.range_changed)
        self.refresh_presets()

    def retranslate(self):
        translate_standard_widgets()
        self.setWindowTitle(t("帧渡视频工具", "ZhenDu Video Tools") + " " + __version__)
        for widget, method, chinese, english in self.bindings:
            getattr(widget, method)(t(chinese, english))
        for widget, choices in self.combos:
            with QSignalBlocker(widget):
                for index, (_, chinese, english) in enumerate(choices):
                    widget.setItemText(index, t(chinese, english))
        for index, chinese, english in self.tab_titles:
            self.tabs.setTabText(index, t(chinese, english))
        self.task_tree.setHeaderLabels([t("视频", "Video"), t("状态", "Status"), t("进度", "Progress")])
        self.audio_track.setItemText(0, t("全部音轨", "All audio tracks"))
        self.player.retranslate()
        self.refresh_presets()
        self.controls_changed()
        for job in self.jobs.values():
            self.update_job_item(job)
        if not self.jobs:
            self.progress_label.setText(t("准备就绪 · 勾选素材后开始处理", "Ready · check sources and start processing"))
        if self.current_path:
            self.update_preview_title()
        self.refresh_result_actions()

    def refresh_presets(self):
        identifier = self.preset_combo.currentData()
        self.preset_combo.clear()
        for preset in self.store.presets:
            self.preset_combo.addItem(self.store.preset_name(preset), preset["id"])
        index = self.preset_combo.findData(identifier)
        if index >= 0:
            self.preset_combo.setCurrentIndex(index)

    def snapshot(self):
        try:
            config = JobConfig(compress=self.compress.isChecked(), codec=self.codec.currentData(), backend=self.backend.currentData(),
                               speed=self.speed.currentData(), quality=self.quality.value(), width=self.width.value() if self.advanced.isChecked() else 0,
                               height=self.height.value() if self.advanced.isChecked() else 0, fps=self.fps.value() if self.advanced.isChecked() else 0,
                               color_range=self.color.currentData() if self.advanced.isChecked() else "source", audio_mode=self.audio_mode.currentData(),
                               audio_bitrate=self.audio_bitrate.value(), audio_track=self.audio_track.currentData(), container=self.container.currentData(),
                               subtitles=self.subtitles.isChecked(), clip=self.clip.isChecked(), clip_start=parse_time(self.clip_start.text()),
                               clip_end=parse_time(self.clip_end.text()) if self.clip_end.text().strip() else None,
                               split=self.split.isChecked(), split_mode=self.split_mode.currentData(), split_count=self.split_count.value(),
                               split_duration=parse_time(self.split_duration.text()), split_size_mb=self.split_size.value(), size_safe=self.size_safe.isChecked())
            config.validate()
            return config
        except ValueError as error:
            raise UserError("时间格式无效，请使用秒数或 HH:MM:SS。", "Invalid time. Use seconds or HH:MM:SS.") from error

    def apply_config(self, config):
        mappings = ((self.codec, config.codec), (self.backend, config.backend), (self.speed, config.speed), (self.color, config.color_range),
                    (self.audio_mode, config.audio_mode), (self.container, config.container), (self.split_mode, config.split_mode), (self.audio_track, config.audio_track))
        for widget, value in mappings:
            index = widget.findData(value)
            if index >= 0:
                widget.setCurrentIndex(index)
        for widget, value in ((self.compress, config.compress), (self.clip, config.clip), (self.split, config.split),
                              (self.subtitles, config.subtitles), (self.size_safe, config.size_safe)):
            widget.setChecked(value)
        for widget, value in ((self.quality, config.quality), (self.width, config.width), (self.height, config.height), (self.fps, config.fps),
                              (self.audio_bitrate, config.audio_bitrate), (self.split_count, config.split_count), (self.split_size, config.split_size_mb)):
            widget.setValue(value)
        self.clip_start.setText(time_text(config.clip_start))
        self.clip_end.setText(time_text(config.clip_end) if config.clip_end is not None else "")
        self.split_duration.setText(time_text(config.split_duration))
        self.advanced.setChecked(bool(config.width or config.height or config.fps or config.color_range != "source"))
        self._desired_audio_track = config.audio_track
        self.controls_changed()

    def controls_changed(self, *_):
        self.video_settings.setEnabled(self.compress.isChecked())
        self.advanced.setEnabled(self.compress.isChecked())
        self.advanced_video.setVisible(self.advanced.isChecked())
        self.advanced_video.setEnabled(self.compress.isChecked())
        self.zero_hint.setVisible(self.advanced.isChecked())
        self.audio_bitrate.setEnabled(self.audio_mode.currentData() == "encode")
        self.clip_start.setEnabled(self.clip.isChecked())
        self.clip_end.setEnabled(self.clip.isChecked())
        self.split_mode.setEnabled(self.split.isChecked())
        mode = self.split_mode.currentData()
        self.split_count.setEnabled(self.split.isChecked() and mode == "count")
        self.split_duration.setEnabled(self.split.isChecked() and mode == "duration")
        self.split_size.setEnabled(self.split.isChecked() and mode == "size")
        self.size_safe.setEnabled(self.split.isChecked() and mode == "size")
        parts = [t("视频重编码", "Video encoding") if self.compress.isChecked() else t("视频流复制 · 无重新编码", "Video stream copy · no re-encoding")]
        if self.clip.isChecked():
            parts.append(t("先截取 A/B", "Trim A/B first"))
        if self.split.isChecked():
            parts.append(t("再分割", "Then split") if self.clip.isChecked() else t("分割", "Split"))
        self.summary.setText(" · ".join(parts))
        self.range_changed()

    def range_changed(self, *_):
        if self.previewing_result:
            self.player.update_range(0, self.player.duration)
            return
        try:
            start = parse_time(self.clip_start.text()) if self.clip.isChecked() else 0.0
            end = parse_time(self.clip_end.text()) if self.clip.isChecked() and self.clip_end.text().strip() else self.player.duration
            self.player.update_range(start, end)
        except ValueError:
            pass

    def set_a(self, seconds):
        if self.previewing_result:
            return
        self.clip.setChecked(True)
        self.clip_start.setText(time_text(seconds))
        self.tabs.setCurrentIndex(1)

    def set_b(self, seconds):
        if self.previewing_result:
            return
        self.clip.setChecked(True)
        self.clip_end.setText(time_text(seconds))
        self.tabs.setCurrentIndex(1)

    def reset_range(self):
        self.clip_start.setText("00:00:00.000")
        self.clip_end.setText(time_text(self.player.duration) if self.player.duration else "")

    def player_loaded(self, duration):
        if self.previewing_result:
            self.range_changed()
            return
        if not self.clip_end.text():
            self.clip_end.setText(time_text(duration))
        self.range_changed()

    def add_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(self, t("添加视频", "Add videos"), "", t("视频文件", "Video files") + " (*.mp4 *.mkv *.mov *.avi *.webm *.m4v *.ts *.mts *.m2ts *.flv *.wmv *.mpg *.mpeg);;" + t("全部文件", "All files") + " (*)")
        self.add_files(files)

    def add_files(self, paths):
        first = None
        for path in paths:
            source = str(Path(path).resolve())
            if not Path(source).is_file() or source in self.files:
                continue
            item = QTreeWidgetItem([Path(source).name])
            item.setToolTip(0, source)
            item.setData(0, Qt.ItemDataRole.UserRole, source)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked)
            self.files[source] = item
            self.file_tree.addTopLevelItem(item)
            first = first or item
        if first:
            self.file_tree.setCurrentItem(first)

    def remove_files(self):
        for item in self.file_tree.selectedItems():
            source = item.data(0, Qt.ItemDataRole.UserRole)
            self.file_tree.takeTopLevelItem(self.file_tree.indexOfTopLevelItem(item))
            self.files.pop(source, None)
        if not self.files and not self.previewing_result:
            self.player.clear()
            self.current_path = ""
            self.source_title.setText(t("预览", "Preview"))
            self.info_label.clear()

    def select_preview(self, item, previous):
        if not item:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        self.load_preview(path)

    def update_preview_title(self):
        name = Path(self.current_path).name
        self.source_title.setText(t("处理结果 · {name}", "Result · {name}", name=name) if self.previewing_result else name)

    def load_preview(self, path, result=False):
        if path == self.current_path and result == self.previewing_result:
            return
        returning_to_source = self.previewing_result and not result and path == self._source_preview_path
        if not self.previewing_result:
            self._source_preview_path = self.current_path
            if result:
                self._desired_audio_track = self.audio_track.currentData()
        self.previewing_result = result
        self.current_path = path
        self.update_preview_title()
        self.info_label.setText(t("读取媒体信息…", "Reading media information…"))
        if not result and not returning_to_source:
            self.clip_start.setText("00:00:00.000")
            self.clip_end.clear()
        self.player.set_editing_enabled(not result)
        self.player.load(path)
        if path in self.probes:
            return
        task = ProbeTask(path, self.cache)
        task.signals.ready.connect(self.probe_ready)
        task.signals.failed.connect(self.probe_failed)
        self.probes[path] = task
        self.pool.start(task)

    def probe_ready(self, path, info):
        self.media_infos[path] = info
        self.probes.pop(path, None)
        if path != self.current_path:
            return
        self.info_label.setText(f"{info.width} × {info.height}  ·  {info.fps:.3f} fps  ·  {time_text(info.duration)}  ·  {info.size / 1024**2:.1f} MiB  ·  {info.video_codec.upper()}")
        if self.previewing_result:
            return
        self.audio_track.clear()
        self.audio_track.addItem(t("全部音轨", "All audio tracks"), -1)
        for index, audio in enumerate(info.audio):
            tags = audio.get("tags", {})
            self.audio_track.addItem(f"{index + 1} · {audio.get('codec_name', '')} · {tags.get('language', '')} {tags.get('title', '')}".strip(), index)
        index = self.audio_track.findData(getattr(self, "_desired_audio_track", -1))
        if index >= 0:
            self.audio_track.setCurrentIndex(index)
        if not self.clip_end.text():
            self.clip_end.setText(time_text(info.duration))

    def probe_failed(self, path, message):
        self.probes.pop(path, None)
        self.append_log(message)
        if path == self.current_path:
            self.info_label.setText(t("媒体信息读取失败，查看日志。", "Unable to read media information; see the log."))

    def apply_selected_preset(self):
        self.apply_preset(self.preset_combo.currentData())

    def apply_preset(self, identifier):
        preset = self.store.get_preset(identifier)
        if not preset:
            raise UserError("预设不存在或已删除。", "The preset no longer exists.")
        try:
            value = asdict(self.snapshot())
        except UserError:
            value = asdict(JobConfig())
        value.update(preset["settings"])
        self.apply_config(JobConfig.from_dict(value))
        self.preset_combo.setCurrentIndex(self.preset_combo.findData(identifier))

    def save_preset(self):
        try:
            dialog = SavePresetDialog(self.store, self.snapshot(), self.preset_combo.currentData(), self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.refresh_presets()
                self.shell.refresh_if_owned()
        except Exception as error:
            error_message(self, error)

    def manage_presets(self):
        dialog = PresetManager(self.store, self.shell, self)
        dialog.chosen.connect(self.apply_preset)
        dialog.exec()
        self.refresh_presets()

    def open_settings(self):
        dialog = SettingsDialog(self.store, self.shell, self)
        dialog.changed.connect(self.retranslate)
        dialog.exec()

    def browse_output(self):
        path = QFileDialog.getExistingDirectory(self, t("选择输出文件夹", "Choose output folder"), self.output_dir.text())
        if path:
            self.output_dir.setText(path)

    def start_processing(self):
        try:
            sources = [path for path, item in self.files.items() if item.checkState(0) == Qt.CheckState.Checked]
            if not sources:
                raise UserError("请添加并勾选要处理的视频。", "Add and check the videos to process.")
            config = self.snapshot()
            self.store.data["output_dir"] = self.output_dir.text().strip()
            self.store.save()
            self.enqueue(sources, config)
        except Exception as error:
            error_message(self, error)

    def enqueue(self, sources, config, output_root=None, task_subfolders=None):
        self.player.media.pause()
        for source in sources:
            task = Task(uuid.uuid4().hex, str(Path(source).resolve()), JobConfig.from_dict(asdict(config)),
                        self.output_dir.text().strip() if output_root is None else output_root,
                        self.store.data.get("task_subfolders", False) if task_subfolders is None else task_subfolders,
                        str(self.store.root / "tasks"))
            item = QTreeWidgetItem([Path(source).name, "", "0%"])
            item.setData(0, Qt.ItemDataRole.UserRole, task.identifier)
            item.setToolTip(0, str(source))
            self.task_tree.addTopLevelItem(item)
            self.jobs[task.identifier] = {"task": task, "item": item, "status": "queued", "fraction": 0.0, "result": None}
            self.update_job_item(self.jobs[task.identifier])
            self.task_queue.put(task)
        self.ensure_worker()

    def ensure_worker(self):
        if self.worker and self.worker.isRunning():
            return
        if self.task_queue.empty():
            return
        self.worker = TaskWorker(self.task_queue, self.cache, self)
        self.worker.started_task.connect(self.job_started)
        self.worker.progress.connect(self.job_progress)
        self.worker.completed.connect(self.job_complete)
        self.worker.failed.connect(self.job_failed)
        self.worker.log.connect(self.append_log)
        self.worker.finished.connect(self.worker_finished)
        self.worker.start()
        self.refresh_result_actions()

    def job_started(self, identifier, path):
        job = self.jobs[identifier]
        job["status"] = "running"
        self.update_job_item(job)
        self.append_log(t("开始处理：{name}", "Processing: {name}", name=Path(path).name))

    def job_progress(self, identifier, data):
        job = self.jobs[identifier]
        job["fraction"] = data["fraction"]
        self.update_job_item(job)
        overall = sum(item["fraction"] for item in self.jobs.values()) / max(len(self.jobs), 1)
        self.progress_bar.setValue(round(overall * 1000))
        speed = data.get("speed", "")
        self.progress_label.setText(f"{Path(job['task'].source).name} · {data['stage']} · {data['fraction'] * 100:.1f}%  {speed}")

    def job_complete(self, identifier, result):
        job = self.jobs[identifier]
        job.update(status="complete", fraction=1.0, result=result)
        for path in result.outputs:
            child = QTreeWidgetItem([Path(path).name, "", ""])
            child.setData(0, Qt.ItemDataRole.UserRole, identifier)
            child.setData(0, Qt.ItemDataRole.UserRole + 1, path)
            child.setToolTip(0, path)
            job["item"].addChild(child)
        job["item"].setExpanded(True)
        self.update_job_item(job)
        self.refresh_result_actions()
        self.append_log(t("完成：{n} 个文件，{size:.2f} MiB，用时 {seconds:.1f} 秒。", "Complete: {n} files, {size:.2f} MiB, {seconds:.1f} seconds.", n=len(result.outputs), size=result.output_size / 1024**2, seconds=result.elapsed))

    def job_failed(self, identifier, message, cancelled=False):
        job = self.jobs[identifier]
        job.update(status="cancelled" if cancelled else "error", fraction=1.0)
        job["item"].setToolTip(1, message)
        self.update_job_item(job)
        self.refresh_result_actions()
        self.append_log(message)

    def update_job_item(self, job):
        labels = {"queued": ("排队", "Queued"), "running": ("处理中", "Running"), "complete": ("完成", "Complete"), "error": ("失败", "Failed"), "cancelled": ("已取消", "Cancelled")}
        job["item"].setText(1, t(*labels[job["status"]]))
        job["item"].setText(2, "—" if job["status"] in {"error", "cancelled"} else f"{job['fraction'] * 100:.0f}%")
        for index in range(job["item"].childCount()):
            job["item"].child(index).setText(1, t("输出文件", "Output file"))

    def worker_finished(self):
        finished = self.sender()
        if finished is not self.worker:
            if finished:
                finished.deleteLater()
            return
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        successful = sum(job["status"] == "complete" for job in self.jobs.values())
        failed = sum(job["status"] == "error" for job in self.jobs.values())
        self.progress_label.setText(t("任务结束 · 完成 {done} · 失败 {failed}", "Tasks finished · complete {done} · failed {failed}", done=successful, failed=failed))
        self.progress_bar.setValue(round(sum(job["fraction"] for job in self.jobs.values()) / max(len(self.jobs), 1) * 1000))
        self.ensure_worker()
        self.refresh_result_actions()

    def result_paths(self, selected=True):
        paths = []
        items = self.task_tree.selectedItems() if selected else [job["item"] for job in self.jobs.values()]
        for item in items:
            job = self.jobs.get(item.data(0, Qt.ItemDataRole.UserRole))
            if not job or job["status"] != "complete" or not job["result"]:
                continue
            output = item.data(0, Qt.ItemDataRole.UserRole + 1)
            paths.extend([output] if output else job["result"].outputs)
        # Parent + child selection must not copy the same file twice.
        return list(dict.fromkeys(paths))

    def refresh_result_actions(self):
        if not hasattr(self, "cancel_button"):
            return
        selected = self.result_paths()
        self.copy_result_button.setEnabled(bool(selected))
        self.open_video_button.setEnabled(bool(selected))
        self.preview_result_button.setEnabled(bool(selected))
        active = self.worker is not None or not self.task_queue.empty()
        copying = bool(self.jobs) and not active
        self.cancel_button.setText(t("复制文件", "Copy files") if copying else t("取消任务", "Cancel tasks"))
        self.cancel_button.setEnabled(active or bool(self.result_paths(False)))
        object_name = "primary" if copying else "danger"
        if self.cancel_button.objectName() != object_name:
            self.cancel_button.setObjectName(object_name)
            self.cancel_button.style().unpolish(self.cancel_button)
            self.cancel_button.style().polish(self.cancel_button)
        self.cancel_button.setToolTip(t("复制本次队列中所有已完成的视频，可直接粘贴到资源管理器。", "Copy all completed videos in this queue for pasting into File Explorer.") if copying else "")

    def task_footer_action(self):
        if self.worker is not None or not self.task_queue.empty():
            self.cancel_tasks()
        else:
            self.copy_result_files(self.result_paths(False))

    def copy_selected_results(self):
        self.copy_result_files(self.result_paths())

    def copy_result_files(self, paths):
        if not paths:
            return
        missing = [path for path in paths if not Path(path).is_file()]
        if missing:
            error_message(self, UserError("文件已移动或删除，请重新选择：\n{path}", "Files were moved or deleted. Select again:\n{path}", path="\n".join(missing)))
            return
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(Path(path).resolve())) for path in paths])
        # Qt maps local URLs to Windows CF_HDROP. Explicitly request copy, never cut.
        mime.setData('application/x-qt-windows-mime;value="Preferred DropEffect"', (1).to_bytes(4, "little"))
        QApplication.clipboard().setMimeData(mime)
        self.progress_label.setText(t("已复制 {n} 个视频文件 · 可直接粘贴", "Copied {n} video files · ready to paste", n=len(paths)))

    def choose_result(self, preview=False):
        paths = self.result_paths()
        if not paths:
            return None
        if len(paths) > 1:
            choices = [f"{index + 1}. {Path(path).name}" for index, path in enumerate(paths)]
            choice, accepted = QInputDialog.getItem(self, t("预览", "Preview") if preview else t("打开视频", "Open video"),
                                                    t("选择视频文件", "Choose a video file"), choices, 0, False)
            if not accepted:
                return None
            path = paths[choices.index(choice)]
        else:
            path = paths[0]
        if not Path(path).is_file():
            error_message(self, UserError("文件已移动或删除：{path}", "File was moved or deleted: {path}", path=path))
            return None
        return path

    def open_result(self):
        if path := self.choose_result():
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve()))):
                error_message(self, UserError("无法打开视频，请检查系统的默认视频播放器。", "Unable to open the video. Check the default video player in Windows."))

    def preview_result(self):
        if path := self.choose_result(preview=True):
            self.load_preview(path, result=True)

    def activate_result(self, item, column=0):
        if item.data(0, Qt.ItemDataRole.UserRole + 1):
            self.preview_result()

    def result_menu(self, point):
        item = self.task_tree.itemAt(point)
        if not item:
            return
        if not item.isSelected():
            self.task_tree.setCurrentItem(item)
        if not self.result_paths():
            return
        menu = QMenu(self)
        for chinese, english, callback in (("复制文件", "Copy files", self.copy_selected_results),
                                           ("打开视频", "Open video", self.open_result),
                                           ("预览", "Preview", self.preview_result),
                                           ("打开输出", "Open output", self.open_output)):
            menu.addAction(t(chinese, english), callback)
        menu.exec(self.task_tree.viewport().mapToGlobal(point))

    def cancel_tasks(self):
        if self.worker:
            self.worker.cancel()
        while True:
            try:
                task = self.task_queue.get_nowait()
            except queue.Empty:
                break
            job = self.jobs[task.identifier]
            job.update(status="cancelled", fraction=1.0)
            self.update_job_item(job)
            self.task_queue.task_done()

    def retry_failed(self):
        for job in list(self.jobs.values()):
            if job["status"] == "error":
                task = job["task"]
                self.enqueue([task.source], task.config, task.output_root, task.task_subfolders)

    def open_output(self):
        item = self.task_tree.currentItem()
        job = self.jobs.get(item.data(0, Qt.ItemDataRole.UserRole)) if item else None
        if job and job["result"]:
            QDesktopServices.openUrl(QUrl.fromLocalFile(job["result"].directory))
        elif self.output_dir.text():
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_dir.text()))

    def append_log(self, message):
        self.log_view.appendPlainText(str(message))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.add_files([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
        event.acceptProposedAction()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            if QMessageBox.question(self, t("退出", "Exit"), t("有任务正在处理，是否取消并退出？", "A task is running. Cancel it and exit?")) != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.cancel_tasks()
            if not self.worker.wait(8000):
                event.ignore()
                return
        for task in list(self.probes.values()):
            task.runner.cancel()
        self.pool.waitForDone(5000)
        self.player.close_player()
        try:
            config = asdict(self.snapshot())
            config.update(clip=False, clip_start=0.0, clip_end=None)
            self.store.data.update(last_config=config, output_dir=self.output_dir.text().strip())
            self.store.save()
        except (OSError, UserError):
            pass
        event.accept()
