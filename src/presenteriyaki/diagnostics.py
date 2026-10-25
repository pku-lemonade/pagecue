"""Opt-in smoke checks run inside the actual distributable executable."""

import json
from pathlib import Path
import platform
import shutil
import sys

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import QEvent, QEventLoop, QLibraryInfo, QObject, QPoint, Qt, QTimer, qVersion
from PySide6.QtGui import QColor, QImage, QKeyEvent
from PySide6.QtWidgets import QApplication

from . import __version__
from .document import Media
from .model import Surface


def capture_audience(presenter):
    window = presenter.audience
    screen = window.screen()
    origin = window.mapToGlobal(QPoint()) - screen.geometry().topLeft()
    return screen.grabWindow(0, origin.x(), origin.y(), window.width(), window.height())


def wait_for_pixels(check):
    """Wait for the native compositor, which finishes after Qt's resize events."""
    loop = QEventLoop()
    poll, deadline = QTimer(), QTimer()
    poll.setInterval(50)
    deadline.setSingleShot(True)
    ready = False
    def inspect():
        nonlocal ready
        ready = check()
        if ready:
            loop.quit()
    poll.timeout.connect(inspect)
    deadline.timeout.connect(loop.quit)
    poll.start()
    deadline.start(5000)
    loop.exec()
    poll.stop()
    deadline.stop()
    assert ready, "Native web camera composition did not render as expected"


def check_web_camera(presenter, output):
    """Inspect synthetic compositing only; never starts or photographs a camera."""
    p = presenter
    assert not p.camera.active and p.slide.camera_image is None
    image = QImage(400, 400, QImage.Format.Format_RGB32)
    image.fill(QColor("#f08030"))
    previous = (p.slide.camera_opacity, p.slide.camera_large, p.audience.size())
    p.audience.raise_()
    p.audience.activateWindow()
    def pixel(point):
        capture = capture_audience(p)
        ratio = capture.devicePixelRatio()
        point = p.web.mapTo(p.audience, point)
        return capture.toImage().pixelColor(round(point.x() * ratio), round(point.y() * ratio))
    def inset():
        return p.web.rect().bottomRight() - QPoint(30, 30)
    def blended(point):
        color = pixel(point)
        return abs(color.red() - 132) <= 3 and abs(color.green() - 92) <= 3
    try:
        p.slide.camera_opacity = .5
        wait_for_pixels(lambda: pixel(inset()).name() == "#18372b")
        capture_audience(p).save(str(Path(output) / "web.png"))
        p.slide.camera_image = image
        p.session.changed.emit()
        wait_for_pixels(lambda: blended(inset()))
        assert p.web.camera.windowFlags() & Qt.WindowType.WindowTransparentForInput
        p.audience.resize(800, 500)
        wait_for_pixels(lambda: blended(inset()))
        capture_audience(p).save(str(Path(output) / "web-camera.png"))
        p.slide.camera_large = True
        p.session.changed.emit()
        wait_for_pixels(lambda: blended(p.web.rect().center()))
        p.slide.camera_image = None
        p.session.changed.emit()
        wait_for_pixels(lambda: pixel(inset()).name() == "#18372b")
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
                        "application_name": presenter.app.applicationName(),
                        "display_name": presenter.app.applicationDisplayName(),
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
        html = self.output / "web-fixture.html"
        video = ""
        if self.media:
            shutil.copyfile(self.media, self.output / "web-video.mp4")
            video = ('<video id="video" src="web-video.mp4" width="160" autoplay muted loop></video>'
                     '<script>window.framesPresented=0;const v=document.querySelector("video");'
                     'const frame=()=>{framesPresented++;v.requestVideoFrameCallback(frame)};'
                     'v.requestVideoFrameCallback(frame);</script>')
        html.write_text('<!doctype html><title>Presenteriyaki packaged web check</title>'
                        '<body style="background:#18372b;color:white;font:24px sans-serif">'
                        '<h1>Packaged offline web content</h1>' + video + '</body>')
        p = self.presenter
        p.open_web(str(html))
        def loaded(okay):
            p.web.loadFinished.disconnect(loaded)
            if not okay:
                self.finish("Packaged native browser failed to load local content")
                return
            QTimer.singleShot(200, lambda: self.guard(self._after_web))
        p.web.loadFinished.connect(loaded)

    def _after_web(self):
        p = self.presenter
        p.web.setZoomFactor(1.5)
        self.key(p.view, Qt.Key.Key_0)
        assert p.web.zoomFactor() == 1.0, "Web zoom reset failed"
        self.results["web_zoom_reset"] = True
        check_web_camera(p, self.output)
        self.results["web_camera_overlay"] = True
        self._web_state()

    def _web_state(self):
        def received(value):
            self.guard(lambda: self._check_web_state(json.loads(value)))
        self.presenter.web.page().runJavaScript(
            "JSON.stringify({title:document.title,agent:navigator.userAgent,"
            "frames:window.framesPresented||0,error:document.querySelector('video')?.error?.message||null})", received)

    def _check_web_state(self, state):
        assert state["title"] == "Presenteriyaki packaged web check", "Unexpected packaged web document title"
        assert state["error"] is None, state["error"]
        self.results["web_user_agent"] = state["agent"]
        if self.media:
            previous = self.results.setdefault("web_initial_video_frames", state["frames"])
            if not state["frames"] or state["frames"] <= previous:
                QTimer.singleShot(200, self._web_state)
                return
            self.results["web_video_frames"] = state["frames"]
            self.results["web_video_decoded"] = True
        self.results["web_loaded"] = True
        self.key(self.presenter.web.native, Qt.Key.Key_Escape)
        QTimer.singleShot(0, self._web_escaped)

    def _web_escaped(self):
        self.results["web_escape"] = self.presenter.session.surface == Surface.SLIDES
        self.finish(None if self.results["web_escape"] else "Web keyboard routing failed")

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
