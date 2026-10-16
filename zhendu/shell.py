import hashlib
import os
from pathlib import Path
import subprocess
import sys

from . import APP_ID
from .language import UserError, t
from .paths import app_root


EXTENSIONS = (".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".ts", ".mts", ".m2ts", ".flv", ".wmv", ".mpg", ".mpeg")
CLASSES = "Software\\Classes\\"
MENU_KEY = APP_ID + ".ContextMenu"
OWNER_KEY = "Software\\ZhenDu\\ShellIntegration"


class Registry:
    def __init__(self):
        if os.name != "nt":
            raise UserError("右键菜单功能仅支持 Windows。", "Explorer integration is available on Windows only.")
        import winreg
        self.reg = winreg

    def set(self, path, name, value):
        with self.reg.CreateKeyEx(self.reg.HKEY_CURRENT_USER, path, 0, self.reg.KEY_WRITE) as key:
            self.reg.SetValueEx(key, name, 0, self.reg.REG_SZ, str(value))

    def get(self, path, name):
        try:
            with self.reg.OpenKey(self.reg.HKEY_CURRENT_USER, path) as key:
                return self.reg.QueryValueEx(key, name)[0]
        except FileNotFoundError:
            return None

    def delete_tree(self, path):
        try:
            with self.reg.OpenKey(self.reg.HKEY_CURRENT_USER, path, 0, self.reg.KEY_READ | self.reg.KEY_WRITE) as key:
                children = []
                while True:
                    try:
                        children.append(self.reg.EnumKey(key, len(children)))
                    except OSError:
                        break
            for child in children:
                self.delete_tree(path + "\\" + child)
            self.reg.DeleteKey(self.reg.HKEY_CURRENT_USER, path)
        except FileNotFoundError:
            pass


def launch_prefix():
    if getattr(sys, "frozen", False):
        return [sys.executable]
    interpreter = Path(sys.executable).with_name("pythonw.exe")
    return [str(interpreter if interpreter.exists() else Path(sys.executable)), str(app_root() / "video_tool_clip_player.py")]


class ShellIntegration:
    def __init__(self, store, registry=None, root=None):
        self.store = store
        self.registry = registry or Registry()
        self.root = str(Path(root or app_root()).resolve())
        self.instance = hashlib.sha256(self.root.casefold().encode("utf-8")).hexdigest()[:24]

    def owner(self):
        return self.registry.get(OWNER_KEY, "Instance")

    def owns_menu(self):
        return self.owner() == self.instance

    def registered_path(self):
        return self.registry.get(OWNER_KEY, "Path") or ""

    @staticmethod
    def notify():
        if os.name == "nt":
            import ctypes
            ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)

    def register(self):
        # Only this application's namespace is ever deleted or replaced.
        self.registry.delete_tree(CLASSES + MENU_KEY)
        entries = [("000-open", t("打开工具", "Open tool"), [], True)]
        for index, preset in enumerate(self.store.presets):
            if preset.get("context", False):
                entries.append((f"{index + 1:03d}-{preset['id']}", self.store.preset_name(preset),
                                ["--preset", preset["id"], "--run"], True))
        entries.append(("999-manage", t("管理预设…", "Manage presets…"), ["--manage-presets"], False))
        for identifier, title, args, with_file in entries:
            key = CLASSES + MENU_KEY + "\\shell\\" + identifier
            self.registry.set(key, "MUIVerb", title)
            self.registry.set(key, "MultiSelectModel", "Player")
            command = subprocess.list2cmdline(launch_prefix() + args)
            if with_file:
                command += ' "%1"'
            self.registry.set(key + "\\command", "", command)
        icon = str(Path(sys.executable) if getattr(sys, "frozen", False) else app_root() / "assets" / "zhendu.ico")
        for extension in EXTENSIONS:
            key = CLASSES + "SystemFileAssociations\\" + extension + "\\shell\\" + APP_ID
            self.registry.set(key, "MUIVerb", t("通过 帧渡 处理", "Process with ZhenDu"))
            self.registry.set(key, "Icon", icon)
            self.registry.set(key, "ExtendedSubCommandsKey", MENU_KEY)
            self.registry.set(key, "MultiSelectModel", "Player")
        self.registry.set(OWNER_KEY, "Instance", self.instance)
        self.registry.set(OWNER_KEY, "Path", self.root)
        self.notify()

    def refresh_if_owned(self):
        if self.owns_menu():
            self.register()

    def unregister(self, force=False):
        if not self.owner():
            return
        if not force and not self.owns_menu():
            raise UserError("菜单由另一版本注册，未移除：{path}", "The menu belongs to another version and was not removed: {path}", path=self.registered_path())
        for extension in EXTENSIONS:
            self.registry.delete_tree(CLASSES + "SystemFileAssociations\\" + extension + "\\shell\\" + APP_ID)
        self.registry.delete_tree(CLASSES + MENU_KEY)
        self.registry.delete_tree(OWNER_KEY)
        self.notify()
