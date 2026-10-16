import ctypes
import locale
import os


def system_language(language_id=None):
    if language_id is None and os.name == "nt":
        try:
            language_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        except (AttributeError, OSError):
            pass
    if language_id is not None:
        return "zh_CN" if language_id & 0x3FF == 0x04 else "en"
    name = (locale.getlocale()[0] or "").lower()
    return "zh_CN" if name.startswith("zh") or "chinese" in name else "en"


class Language:
    selection = "auto"

    @property
    def current(self):
        return system_language() if self.selection == "auto" else self.selection

    def text(self, chinese, english, **values):
        return (chinese if self.current == "zh_CN" else english).format(**values)

    def automatic_label(self):
        return "自动选择(简体中文)" if system_language() == "zh_CN" else "Automatic (English)"


language = Language()
t = language.text


def translate_standard_widgets():
    from PySide6.QtCore import QLibraryInfo, QTranslator
    from PySide6.QtWidgets import QApplication
    from .paths import resource_path
    app = QApplication.instance()
    if not app:
        return
    previous = getattr(app, "zhendu_translator", None)
    if previous:
        app.removeTranslator(previous)
        previous.deleteLater()
    app.zhendu_translator = None
    if language.current == "zh_CN":
        translator = QTranslator(app)
        path = resource_path("assets/qtbase_zh_CN.qm")
        loaded = translator.load(str(path)) if path.is_file() else translator.load("qtbase_zh_CN", QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))
        if loaded:
            app.installTranslator(translator)
            app.zhendu_translator = translator


class UserError(Exception):
    def __init__(self, chinese, english, **values):
        self.chinese = chinese
        self.english = english
        self.values = values
        super().__init__(english.format(**values))

    def localized(self):
        return t(self.chinese, self.english, **self.values)
