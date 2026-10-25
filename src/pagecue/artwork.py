"""Render PageCue's original geometric artwork without opening a window."""

from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer


def icon_png(size=256):
    # The bundled SVG contains only geometric shapes; no font database or GUI
    # application is needed to paint it into an image, including in CLI tools.
    renderer = QSvgRenderer(str(Path(__file__).parent / "assets/pagecue.svg"))
    if not renderer.isValid():
        raise RuntimeError("The bundled PageCue icon could not be read")
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    try:
        renderer.render(painter, QRectF(0, 0, size, size))
    finally:
        painter.end()
    output = QBuffer()
    output.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(output, "PNG"):
        raise RuntimeError("Could not encode the PageCue icon")
    return bytes(output.data())
