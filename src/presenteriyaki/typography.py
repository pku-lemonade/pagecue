"""Stable UI fonts and pixel-based sizes across desktop backends."""

from functools import lru_cache
from PySide6.QtGui import QFont, QFontDatabase


@lru_cache(maxsize=1)
def family():
    available = set(QFontDatabase.families())
    return next((name for name in ("Helvetica Neue", "Segoe UI", "Noto Sans", "DejaVu Sans", "Arial")
                 if name in available), QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family())


def ui_font(pixels):
    font = QFont(family())
    font.setPixelSize(max(8, round(pixels)))
    return font
