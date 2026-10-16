"""Render the editable SVG and package standard PNG-backed Windows icon sizes."""
from pathlib import Path
import struct
import sys

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

root = Path(__file__).resolve().parent.parent
app = QApplication(sys.argv[:1])
renderer = QSvgRenderer(str(root / "assets" / "zhendu.svg"))
images = []
for size in (16, 24, 32, 48, 64, 128, 256):
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    images.append((size, bytes(data)))
    if size == 256:
        image.save(str(root / "assets" / "zhendu.png"))
offset = 6 + len(images) * 16
header = struct.pack("<HHH", 0, 1, len(images))
entries = []
for size, data in images:
    entries.append(struct.pack("<BBBBHHII", size if size < 256 else 0, size if size < 256 else 0, 0, 0, 1, 32, len(data), offset))
    offset += len(data)
(root / "assets" / "zhendu.ico").write_bytes(header + b"".join(entries) + b"".join(data for _, data in images))
print("Created assets/zhendu.ico (7 sizes), assets/zhendu.png")
