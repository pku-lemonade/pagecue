"""Capture responsive layouts and synthetic camera compositing without device access."""

import argparse
import json
from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QSettings, Qt, QTimer
from PySide6.QtGui import QColor, QImage, QPainter, QWheelEvent

from pagecue.app import Application, Presenter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(output / "settings"))
    app = Application([])
    app.setStyle("Fusion")
    presenter = Presenter(app)
    presenter.show()
    presenter.open(args.pdf)
    presenter.presenter.resize(700, 420)
    results = {"passed": False, "synthetic_camera_only": True}
    def save(name, widget):
        if not widget.grab().save(str(output / f"{name}.png")):
            raise RuntimeError(f"Could not save {name} capture")
    def scroll_help():
        presenter.view.repaint()
        save("minimum", presenter.presenter)
        page = presenter.session.page
        position = presenter.view.help_box.center()
        event = QWheelEvent(position, QPointF(presenter.view.mapToGlobal(position.toPoint())), QPoint(),
                            QPoint(0, -1200), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                            Qt.ScrollPhase.NoScrollPhase, False)
        app.sendEvent(presenter.view, event)
        presenter.view.repaint()
        results["help_scrolled"] = presenter.view.help_scroll > 0
        results["scroll_preserved_page"] = presenter.session.page == page
        save("minimum-scrolled", presenter.presenter)
        presenter.presenter.resize(1180, 780)
        presenter.view.help_scroll = 0
        QTimer.singleShot(500, lambda: guard(large))
    def large():
        save("normal", presenter.presenter)
        image = QImage(640, 360, QImage.Format.Format_RGB32)
        image.fill(QColor("#ef8e56"))
        painter = QPainter(image)
        painter.setPen(QColor("#30251b"))
        painter.drawEllipse(200, 60, 240, 240)
        painter.end()
        # Inject a drawn image directly into the canvases; Camera.start is never called.
        presenter.view.camera_image = presenter.slide.camera_image = image
        presenter.set_camera_appearance(.45, .65, "top-left")
        QTimer.singleShot(200, lambda: guard(camera))
    def camera():
        save("camera-inset", presenter.audience)
        presenter.view.camera_large = presenter.slide.camera_large = True
        presenter.session.changed.emit()
        QTimer.singleShot(200, lambda: guard(finish))
    def finish():
        save("camera-expanded", presenter.audience)
        results["passed"] = results["help_scrolled"] and results["scroll_preserved_page"]
        close()
    def close():
        (output / "result.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        presenter.quit()
    def guard(callback):
        try:
            callback()
        except Exception as error:
            results["error"] = str(error)
            close()
    def ready():
        if any(key[0] == presenter.session.page and key[1] >= 500 for key in presenter.session.images.cache):
            guard(scroll_help)
        else:
            QTimer.singleShot(100, ready)
    def timeout():
        if not results["passed"]:
            results["error"] = "Timed out waiting for the layout check"
            close()
    QTimer.singleShot(20000, timeout)
    QTimer.singleShot(100, ready)
    app.exec()
    if not results["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
