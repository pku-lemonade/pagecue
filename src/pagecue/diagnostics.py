"""Opt-in smoke checks run inside the actual distributable executable."""

import json
from pathlib import Path
import platform
import sys

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QEvent, QLibraryInfo, QObject, QPoint, Qt, QTimer, qVersion
from PySide6.QtGui import QColor, QImage, QKeyEvent
from PySide6.QtWidgets import QApplication

from . import __version__
from .document import Media
from .model import Surface


def check_web_camera(presenter, output):
    """Inspect synthetic compositing only; never starts or photographs a camera."""
    p = presenter
    assert not p.camera.active and p.slide.camera_image is None
    image = QImage(400, 400, QImage.Format.Format_RGB32)
    image.fill(QColor("#f08030"))
    previous = (p.slide.camera_opacity, p.slide.camera_large, p.audience.size())
    try:
        p.slide.camera_image = image
        p.slide.camera_opacity = .5
        p.session.changed.emit()
        def pixel(x, y):
            capture = p.audience.grab()
            ratio = capture.devicePixelRatio()
            return capture.toImage().pixelColor(round(x * ratio), round(y * ratio))
        def inset_check():
            box = p.slide.geometry()
            point = box.bottomRight() - QPoint(30, 30)
            color = pixel(point.x(), point.y())
            # Half-opacity orange over the known green HTML background.
            assert abs(color.red() - 132) <= 3 and abs(color.green() - 92) <= 3, color.name()
            target = p.audience.childAt(point)
            assert target is p.web or p.web.isAncestorOf(target), "Camera blocks web input"
        inset_check()
        p.audience.resize(800, 500)
        QApplication.processEvents()
        inset_check()
        p.audience.grab().save(str(Path(output) / "web-camera.png"))
        p.slide.camera_large = True
        p.session.changed.emit()
        center = p.slide.geometry().center()
        assert abs(pixel(center.x(), center.y()).red() - 132) <= 3, "Expanded camera hidden"
        p.slide.camera_image = None
        p.session.changed.emit()
        point = p.slide.geometry().bottomRight()
        assert pixel(point.x() - 30, point.y() - 30).name() == "#18372b", "Stale camera after stop"
    finally:
        p.slide.camera_image = None
        p.slide.camera_opacity, p.slide.camera_large, size = previous
        p.audience.resize(size)
        p.session.changed.emit()


class SmokeCheck(QObject):
    def __init__(self, presenter, output, media=None, web=False):
        super().__init__(presenter)
        self.presenter = presenter
        self.output = Path(output).resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.media = Path(media).resolve() if media else None
        self.web = web
        self.results = {"version": __version__, "qt": qVersion(), "platform": platform.platform(),
                        "python": platform.python_version(), "pyside": pyside_version, "qt_build": QLibraryInfo.build(),
                        "architecture": platform.machine(), "frozen": bool(getattr(sys, "frozen", False)), "passed": False}
        self.done = False
        self.poll = QTimer(self)
        self.poll.setInterval(50)
        self.poll.timeout.connect(self._ready)
        self.deadline = QTimer(self)
        self.deadline.setSingleShot(True)
        self.deadline.timeout.connect(lambda: self.finish("Smoke check timed out"))
        self.deadline.start(60000)
        self.poll.start()

    def guard(self, callback):
        try:
            callback()
        except Exception as error:
            self.finish(f"{type(error).__name__}: {error}")

    def _ready(self):
        session = self.presenter.session
        if session.snapshot is not None and session.images.cache:
            self.poll.stop()
            self.guard(self._presentation)

    def key(self, widget, key):
        QApplication.sendEvent(widget, QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier))

    def _presentation(self):
        p = self.presenter
        p.presenter.grab().save(str(self.output / "presenter.png"))
        p.audience.grab().save(str(self.output / "audience.png"))
        self.results["pages"] = p.session.navigation.count
        self.results["notes_pages"] = len(p.session.snapshot.notes.pages)
        self.results["rendered"] = True
        old_page = p.session.page
        self.results["initial_page"] = old_page + 1
        self.results["talk_duration_seconds"] = p.session.clock.duration
        self.results["video_routing"] = p.video_mode
        if p.session.navigation.count > 1:
            p.session.go(0)
            self.key(p.view, Qt.Key.Key_Right)
            assert p.session.page == 1, "Presenter navigation failed"
            self.key(p.slide, Qt.Key.Key_Left)
            assert p.session.page == 0, "Audience navigation failed"
        p.session.go(old_page)
        p.session.reload()
        assert p.session.page == old_page, "Reload changed the selected page"
        self.results["navigation_reload"] = True
        if self.media:
            self._media()
        elif self.web:
            self._web()
        else:
            self.finish()

    def _media(self):
        p = self.presenter
        p.media.audio.setMuted(True)
        def decoded(image):
            p.media.frame.disconnect(decoded)
            p.media.pause()
            self.results["media_decoded"] = not image.isNull()
            QTimer.singleShot(100, lambda: self.guard(self._after_media))
        p.media.frame.connect(decoded)
        p.play_media(Media(self.media.name, path=self.media), (.2, .2, .4, .4))

    def _after_media(self):
        self.presenter.audience.grab().save(str(self.output / "media.png"))
        if self.web:
            self._web()
        else:
            self.finish()

    def _web(self):
        from PySide6.QtWebEngineCore import (qWebEngineVersion, qWebEngineChromiumVersion,
                                            qWebEngineChromiumSecurityPatchVersion)
        self.results.update(qt_webengine=qWebEngineVersion(), chromium=qWebEngineChromiumVersion(),
                            chromium_security_patch=qWebEngineChromiumSecurityPatchVersion())
        html = self.output / "web-fixture.html"
        html.write_text('<!doctype html><title>PageCue packaged web check</title>'
                        '<body style="background:#18372b;color:white;font:24px sans-serif">'
                        '<h1>Packaged offline web content</h1></body>')
        p = self.presenter
        p.open_web(str(html))
        def loaded(okay):
            p.web.loadFinished.disconnect(loaded)
            if not okay:
                self.finish("Packaged WebEngine failed to load local content")
                return
            QTimer.singleShot(200, lambda: self.guard(self._after_web))
        p.web.loadFinished.connect(loaded)

    def _after_web(self):
        p = self.presenter
        p.web.setZoomFactor(1.5)
        self.key(p.view, Qt.Key.Key_0)
        assert p.web.zoomFactor() == 1.0, "Web zoom reset failed"
        self.results["web_zoom_reset"] = True
        p.audience.grab().save(str(self.output / "web.png"))
        check_web_camera(p, self.output)
        self.results["web_camera_overlay"] = True
        def title(value):
            if value != "PageCue packaged web check":
                self.finish("Unexpected packaged web document title")
                return
            self.key(p.web.focusProxy() or p.web, Qt.Key.Key_Escape)
            self.results["web_loaded"] = True
            self.results["web_escape"] = p.session.surface == Surface.SLIDES
            self.finish(None if self.results["web_escape"] else "Web keyboard routing failed")
        p.web.page().runJavaScript("document.title", title)

    def finish(self, error=None):
        if self.done:
            return
        self.done = True
        self.poll.stop()
        self.deadline.stop()
        self.results["passed"] = error is None
        if error:
            self.results["error"] = error
        (self.output / "result.json").write_text(json.dumps(self.results, indent=2))
        QTimer.singleShot(0, self.presenter.quit)
