"""Native WebEngine integration check against an offline original HTML fixture."""

import json
from pathlib import Path
import sys
from PySide6.QtCore import QSettings, QTimer, Qt
from PySide6.QtTest import QTest
from pagecue.app import Application, Presenter
from pagecue.model import Surface


def main():
    deck, output = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(output / "settings"))
    html = output / "local.html"
    html.write_text('<!doctype html><html><head><title>PageCue local web fixture</title></head>'
        '<body style="background:#18372b;color:white;font:30px sans-serif">'
        '<h1>Offline web content</h1><p>A local fixture, not a network request.</p></body></html>')
    app = Application(["pagecue-web-smoke"])
    presenter = Presenter(app)
    presenter.show()
    if not presenter.open(deck):
        raise RuntimeError("Could not open fixture deck")
    result = {}
    def loaded(okay):
        result["loaded"] = okay
        presenter.audience.resize(800, 500)
        def inspect():
            result["web_geometry_matches"] = presenter.web.geometry() == presenter.slide.geometry()
            presenter.audience.grab().save(str(output / "audience.png"))
            def title(value):
                result["title"] = value
                QTest.keyClick(presenter.web, Qt.Key.Key_Escape)
                result["escape_returns_slides"] = presenter.session.surface == Surface.SLIDES
                (output / "results.json").write_text(json.dumps(result, indent=2))
                app.quit()
            presenter.web.page().runJavaScript("document.title", title)
        QTimer.singleShot(500, inspect)
    presenter.open_web(str(html))
    presenter.web.loadFinished.connect(loaded)
    QTimer.singleShot(15000, app.quit)
    app.exec()
    presenter.quit()
    if not result.get("loaded") or not result.get("escape_returns_slides"):
        raise RuntimeError("Web integration smoke check failed or timed out")


if __name__ == "__main__":
    main()
