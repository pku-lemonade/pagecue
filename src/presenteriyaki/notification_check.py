"""Opt-in observation aid for actual OS notification delivery, never run by CI."""

import json
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QTimer

from .services import REPOSITORY


class NotificationCheck(QObject):
    def __init__(self, presenter, output):
        super().__init__(presenter)
        self.presenter = presenter
        self.output = Path(output).resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.result = {"frozen": bool(getattr(sys, "frozen", False)), "requested": False,
                       "clicked": False, "delivery": "Requires observation of the OS notification"}
        self.finished = False
        self.start_timer = QTimer(self)
        self.start_timer.setSingleShot(True)
        self.start_timer.timeout.connect(self.start)
        self.start_timer.start(2000)
        self.deadline = QTimer(self)
        self.deadline.setSingleShot(True)
        self.deadline.timeout.connect(self.finish)
        self.deadline.start(90000)
        presenter.app.aboutToQuit.connect(self.finish)

    def save(self):
        (self.output / "result.json").write_text(json.dumps(self.result, indent=2), encoding="utf-8")

    def start(self):
        self.result["requested"] = self.presenter.desktop_notification(
            "Presenteriyaki notification test", "Local delivery check. Click to open Presenteriyaki's source repository.",
            f"https://github.com/{REPOSITORY}")
        if self.result["requested"]:
            self.presenter.update_tray.messageClicked.connect(self.clicked)
        self.save()

    def clicked(self):
        self.result["clicked"] = True
        self.save()
        QTimer.singleShot(1000, self.finish)

    def finish(self):
        if self.finished:
            return
        self.finished = True
        self.start_timer.stop()
        self.deadline.stop()
        self.save()
        self.presenter.quit()
