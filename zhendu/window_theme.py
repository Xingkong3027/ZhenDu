"""Match Windows-owned title bars to the application's dark client area."""
import ctypes
import os
import sys

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QWidget


def _dwm():
    library = ctypes.WinDLL("dwmapi", use_last_error=True)
    for name in ("DwmSetWindowAttribute", "DwmGetWindowAttribute"):
        function = getattr(library, name)
        function.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
        function.restype = ctypes.c_long
    return library


def apply_title_bar(widget):
    if os.name != "nt":
        return
    handle = int(widget.winId())
    library = _dwm()
    enabled = ctypes.c_int(1)
    # 20 is the current attribute; earlier Windows 10 builds used 19.
    for attribute in (20, 19):
        if library.DwmSetWindowAttribute(handle, attribute, ctypes.byref(enabled), ctypes.sizeof(enabled)) == 0:
            widget._zhendu_dark_title_attribute = attribute
            break
    if sys.getwindowsversion().build >= 22000:
        for attribute, value in ((35, 0x001F1710), (36, 0x00F4EDE5)):
            color = ctypes.c_uint32(value)
            library.DwmSetWindowAttribute(handle, attribute, ctypes.byref(color), ctypes.sizeof(color))


def title_bar_is_dark(widget):
    if os.name != "nt":
        return True
    attribute = getattr(widget, "_zhendu_dark_title_attribute", 20)
    enabled = ctypes.c_int(0)
    return _dwm().DwmGetWindowAttribute(int(widget.winId()), attribute, ctypes.byref(enabled), ctypes.sizeof(enabled)) == 0 and bool(enabled.value)


class WindowTheme(QObject):
    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Show and isinstance(watched, QWidget) and watched.isWindow():
            try:
                apply_title_bar(watched)
            except (OSError, AttributeError):
                pass
        return False


def install_window_theme(app):
    app.zhendu_window_theme = WindowTheme(app)
    app.installEventFilter(app.zhendu_window_theme)
