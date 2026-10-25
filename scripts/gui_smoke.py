"""Exercise the real application and capture its own widgets for visual QA."""

import json
from pathlib import Path
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtTest import QTest
from pagecue.app import Application, Presenter


def main():
    path, output = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    app = Application(["pagecue-smoke"])
    app.setApplicationName("PageCue QA")
    presenter = Presenter(app)
    presenter.show()
    if not presenter.open(path):
        raise RuntimeError("Opening the QA document failed")
    results = {}
    def capture():
        if len(presenter.session.images.cache) < 3:
            QTimer.singleShot(100, capture)
            return
        presenter.presenter.grab().save(str(output / "presenter.png"))
        presenter.audience.grab().save(str(output / "audience.png"))
        QTest.keyClick(presenter.view, Qt.Key.Key_Right)
        results["keyboard_page"] = presenter.session.page
        QTest.keyClick(presenter.slide, Qt.Key.Key_Left)
        results["audience_keyboard_page"] = presenter.session.page
        QTest.keyClick(presenter.view, Qt.Key.Key_B)
        results["board"] = presenter.session.surface.value
        QTest.keyClick(presenter.view, Qt.Key.Key_S)
        QTest.keyClick(presenter.view, Qt.Key.Key_T)
        results["timer_running"] = presenter.session.clock.started is not None
        presenter.reload()
        results["reload_kept_timer"] = presenter.session.clock.started is not None
        (output / "smoke.json").write_text(json.dumps(results, indent=2))
        print(json.dumps(results))
        app.quit()
    QTimer.singleShot(100, capture)
    QTimer.singleShot(15000, app.quit)
    app.exec()
    presenter.quit()
    if not results:
        raise RuntimeError("Timed out before rendering completed")


if __name__ == "__main__":
    main()
