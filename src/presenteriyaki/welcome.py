"""First-launch controls."""

import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from .typography import ui_font


MODIFIER = "⌘" if sys.platform == "darwin" else "Ctrl+"


class Welcome(QWidget):
    open_requested = Signal()

    def __init__(self, parent):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.addStretch()
        title = QLabel("Presenteriyaki")
        title.setFont(ui_font(28))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #f3f3f3")
        layout.addWidget(title)
        description = QLabel("Slides for your audience. Notes for you.")
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setStyleSheet("color: #a5abb5")
        layout.addWidget(description)
        self.open_button = QPushButton("Open PDF…")
        self.open_button.setMinimumWidth(180)
        self.open_button.setStyleSheet("""
            QPushButton { background: #e6cf6b; color: #17191d; border: 2px solid #e6cf6b;
                          border-radius: 6px; padding: 10px 24px; font-size: 15px; }
            QPushButton:hover { background: #f0df8b; border-color: #f0df8b; }
            QPushButton:focus { border-color: white; }
        """)
        self.open_button.clicked.connect(self.open_requested)
        layout.addWidget(self.open_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        hint = QLabel(f"{MODIFIER}O  ·  or drop a PDF here")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #858d99")
        layout.addWidget(hint)
        layout.addStretch()
