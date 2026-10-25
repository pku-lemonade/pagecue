"""Explicitly requested device acceptance; metadata only, never camera captures."""

import json
from pathlib import Path

from PySide6.QtCore import QCameraPermission, QObject, QTimer


class HardwareCheck(QObject):
    def __init__(self, presenter, output, camera=False):
        super().__init__(presenter)
        self.presenter = presenter
        self.output = Path(output).resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.use_camera = camera
        self.done = False
        self.results = {"passed": False, "phase": "opening", "camera_requested_by_user": camera,
                        "camera_images_saved": False, "frames": 0, "checks": {}}
        self.screens = presenter.app.screens()
        self.results["displays"] = [
            {"index": index, "width": screen.size().width(), "height": screen.size().height(),
             "dpr": screen.devicePixelRatio()} for index, screen in enumerate(self.screens)]
        presenter.camera.frame.connect(self.frame)
        presenter.camera.error.connect(lambda message: self.finish(message))
        presenter.app.aboutToQuit.connect(self.stopped)
        self.deadline = QTimer(self)
        self.deadline.setSingleShot(True)
        self.deadline.timeout.connect(lambda: self.finish("Hardware check timed out"))
        self.deadline.start(120000)
        self.later(100, self.ready)

    def write(self):
        (self.output / "result.json").write_text(json.dumps(self.results, indent=2), encoding="utf-8")

    def later(self, delay, callback):
        def run():
            if self.done:
                return
            try:
                callback()
                self.write()
            except Exception as error:
                self.finish(f"{type(error).__name__}: {error}")
        QTimer.singleShot(delay, run)

    def check(self, name, value):
        self.results["checks"][name] = bool(value)
        self.results.setdefault("windows", {})[name] = [
            {"role": role, "display": self.screens.index(window.screen()) if window.screen() in self.screens else None,
             "frame": list(window.frameGeometry().getRect()), "screen_frame": list(window.screen().geometry().getRect()),
             "presentation_fullscreen": window.presentation_fullscreen, "qt_fullscreen": window.isFullScreen()}
            for role, window in (("presenter", self.presenter.presenter), ("audience", self.presenter.audience))]

    def ready(self):
        p = self.presenter
        if p.session.snapshot is None or not p.session.images.cache:
            self.later(100, self.ready)
            return
        self.results["phase"] = "audience-fullscreen"
        self.check("two_displays", len(self.screens) >= 2)
        p.audience_screen = self.screens[-1].name()
        p.toggle_fullscreen(audience_only=True)
        self.later(2000, self.audience_fullscreen)

    def audience_fullscreen(self):
        p = self.presenter
        self.check("audience_only_fullscreen", p.audience.presentation_fullscreen and not p.presenter.presentation_fullscreen
                   and p.audience.frameGeometry() == p.audience.screen().geometry())
        self.check("audience_on_selected_display", p.audience.screen() is self.screens[-1])
        self.results["phase"] = "both-fullscreen"
        p.toggle_fullscreen()
        self.later(2000, self.both_fullscreen)

    def both_fullscreen(self):
        p = self.presenter
        self.check("both_fullscreen", p.audience.presentation_fullscreen and p.presenter.presentation_fullscreen
                   and p.audience.frameGeometry() == p.audience.screen().geometry()
                   and p.presenter.frameGeometry() == p.presenter.screen().geometry())
        self.check("separate_displays", p.audience.screen() is not p.presenter.screen())
        self.previous_audience_screen = p.audience.screen()
        self.results["phase"] = "swapped-displays"
        p.swap()
        self.later(2000, self.swapped)

    def swapped(self):
        p = self.presenter
        self.check("swapped_displays", p.presenter.screen() is self.previous_audience_screen
                   and p.audience.screen() is not self.previous_audience_screen)
        self.results["phase"] = "hidden"
        p.hide_all()
        self.later(1000, self.hidden)

    def hidden(self):
        p = self.presenter
        self.check("both_hidden", p.presenter.isMinimized() and p.audience.isMinimized())
        p.restore_all()
        self.results["phase"] = "restored"
        self.later(2000, self.restored)

    def restored(self):
        p = self.presenter
        self.check("fullscreen_restored", p.presenter.presentation_fullscreen and p.audience.presentation_fullscreen
                   and p.presenter.screen() is not p.audience.screen())
        p.leave_fullscreen()
        self.later(2000, self.camera)

    def camera(self):
        p = self.presenter
        self.check("windowed_restored", not p.presenter.presentation_fullscreen and not p.audience.presentation_fullscreen)
        if not self.use_camera:
            self.finish()
            return
        devices = p.camera.devices()
        self.results["camera_device_count"] = len(devices)
        self.results["permission_before"] = p.app.checkPermission(QCameraPermission()).name
        if not devices:
            self.finish("No camera device is available")
            return
        device = next((device for device in devices if device.isDefault()), devices[0])
        self.results["phase"] = "camera-permission"
        p.notify("Local camera check: no images are saved. Allow the macOS prompt if shown.")
        p.camera.start(device)

    def frame(self, image):
        if self.done:
            return
        self.results["frames"] += 1
        if self.results["frames"] == 1:
            self.results["phase"] = "camera-preview"
            self.results["frame_dimensions"] = [image.width(), image.height()]
            self.results["permission_after"] = self.presenter.app.checkPermission(QCameraPermission()).name
            self.presenter.notify("Camera preview test: stops automatically in 15 seconds. No images saved.")
            self.write()
            self.later(15000, self.stop_camera)

    def stop_camera(self):
        p = self.presenter
        self.check("live_camera_frames", self.results["frames"] > 1 and p.camera.active)
        self.check("camera_in_both_views", p.view.camera_image is not None and p.slide.camera_image is not None)
        p.camera.stop()
        self.frames_at_stop = self.results["frames"]
        self.results["phase"] = "camera-stopped"
        self.later(1000, self.camera_stopped)

    def camera_stopped(self):
        p = self.presenter
        self.check("camera_stopped", not p.camera.active and not p.camera.requested)
        self.check("camera_views_cleared", p.view.camera_image is None and p.slide.camera_image is None)
        self.check("no_frames_after_stop", self.results["frames"] == self.frames_at_stop)
        self.finish()

    def finish(self, error=None):
        if self.done:
            return
        self.done = True
        self.deadline.stop()
        self.presenter.camera.stop()
        if self.presenter.fullscreen:
            self.presenter.leave_fullscreen()
        if error:
            self.results["error"] = error
        self.results["phase"] = "finished"
        self.results["passed"] = error is None and all(self.results["checks"].values())
        self.write()
        QTimer.singleShot(0, self.presenter.quit)

    def stopped(self):
        if not self.done:
            self.finish("The application was closed before the check completed")
