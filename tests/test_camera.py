"""Camera permission/lifecycle simulations; these tests never open a real device."""

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QImage
from PySide6.QtMultimedia import QCamera, QVideoFrame
from PIL import Image, ImageChops

from pagecue.app import Presenter
from pagecue import media


@pytest.mark.parametrize("dimensions", [(400, 400), (640, 360), (300, 600)])
def test_default_camera_inset_stays_small_in_bottom_right(qapp, qtbot, deck, dimensions, tmp_path):
    presenter = Presenter(qapp)
    qtbot.addWidget(presenter.presenter)
    qtbot.addWidget(presenter.audience)
    presenter.show()
    presenter.open(deck)
    qtbot.waitUntil(lambda: bool(presenter.session.images.cache) and not presenter.session.images.pending)
    view = presenter.slide
    def capture():
        image = view.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        return Image.frombytes("RGBA", (image.width(), image.height()), bytes(image.constBits()))
    before = capture()
    # A solid synthetic rectangle, never a camera frame or physical device.
    image = QImage(*dimensions, QImage.Format.Format_RGB32)
    image.fill(QColor("#f08030"))
    view.camera_image, view.camera_opacity = image, 1.0
    after = capture()
    bounds = ImageChops.difference(before, after).convert("RGB").getbbox()
    assert bounds is not None
    x1, y1, x2, y2 = bounds
    dpr = view.devicePixelRatioF()
    assert x2 - x1 <= after.width * .20
    assert y2 - y1 <= after.height * .20
    assert abs(after.width - x2 - 16 * dpr) <= 2 * dpr
    assert abs(after.height - y2 - 16 * dpr) <= 2 * dpr
    assert (x2 - x1) / (y2 - y1) == pytest.approx(dimensions[0] / dimensions[1], abs=.03)
    after.save(tmp_path / "synthetic-camera-inset.png")
    presenter.session.close()
    presenter.media.close()


def device(identifier):
    return SimpleNamespace(id=lambda: identifier, description=lambda: identifier.decode())


@pytest.fixture
def simulated_camera(qapp, monkeypatch):
    instances, callbacks = [], []
    devices = [device(b"first"), device(b"second")]
    class Capture(QObject):
        def setCamera(self, camera):
            self.camera = camera
        def setVideoSink(self, sink):
            self.sink = sink
    class NativeCamera(QObject):
        Error = QCamera.Error
        activeChanged = Signal(bool)
        errorOccurred = Signal(object, str)
        def __init__(self, device, parent):
            super().__init__(parent)
            self.device = device
            self.active = False
            instances.append(self)
        def isActive(self):
            return self.active
        def start(self):
            self.active = True
            self.activeChanged.emit(True)
        def stop(self):
            self.active = False
            self.activeChanged.emit(False)
    monkeypatch.setattr(media, "QCamera", NativeCamera)
    monkeypatch.setattr(media, "QMediaCaptureSession", Capture)
    monkeypatch.setattr(media.Camera, "devices", staticmethod(lambda: devices))
    monkeypatch.setattr(qapp, "checkPermission", lambda _: Qt.PermissionStatus.Undetermined)
    def request_permission(permission, context, callback):
        assert isinstance(context, media.Camera)
        callbacks.append(callback)
    monkeypatch.setattr(qapp, "requestPermission", request_permission)
    def reply(index=0, granted=True):
        callbacks[index](SimpleNamespace(status=lambda: Qt.PermissionStatus.Granted if granted else Qt.PermissionStatus.Denied))
    return SimpleNamespace(instances=instances, devices=devices, callbacks=callbacks, reply=reply)


@pytest.mark.parametrize("cancel", ["stop", "device_removed", "denied"])
def test_camera_permission_cancellation_never_opens_device(qapp, simulated_camera, cancel):
    camera = media.Camera()
    camera.start(simulated_camera.devices[0])
    assert camera.requested and not camera.active
    if cancel == "stop":
        camera.stop()
    elif cancel == "device_removed":
        simulated_camera.devices.clear()
        camera.device_monitor.videoInputsChanged.emit()
    simulated_camera.reply(granted=cancel != "denied")
    assert not camera.requested and not camera.active
    assert simulated_camera.instances == []
    camera.stop()


def test_camera_switch_ignores_old_permission_and_frames(qapp, simulated_camera):
    camera = media.Camera()
    camera.start(simulated_camera.devices[0])
    camera.start(simulated_camera.devices[1])
    simulated_camera.reply(0)
    assert not simulated_camera.instances
    simulated_camera.reply(1)
    assert camera.active and camera.camera.device is simulated_camera.devices[1]
    image = QImage(80, 60, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    frame = QVideoFrame(image)
    seen = []
    camera.frame.connect(seen.append)
    old_sink = camera.sink
    old_sink.setVideoFrame(frame)
    assert len(seen) == 1
    camera.start(simulated_camera.devices[0])
    simulated_camera.reply(2)
    old_sink.videoFrameChanged.emit(frame)
    assert len(seen) == 1  # queued frame from the previous capture generation
    camera.sink.setVideoFrame(frame)
    assert len(seen) == 2
    camera.camera.errorOccurred.emit(QCamera.Error.CameraError, "simulated disconnect")
    assert not camera.active and not camera.requested
    camera.stop()


def test_camera_loss_clears_both_views_and_quit_cancels_permission(qapp, qtbot, deck, monkeypatch, simulated_camera):
    simulated_camera.devices[:] = simulated_camera.devices[:1]
    presenter = Presenter(qapp)
    qtbot.addWidget(presenter.presenter)
    qtbot.addWidget(presenter.audience)
    presenter.open(deck)
    presenter.toggle_camera()
    simulated_camera.reply()
    image = QImage(80, 60, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    presenter.camera.sink.setVideoFrame(QVideoFrame(image))
    assert presenter.view.camera_image is not None and presenter.slide.camera_image is not None
    disconnected = simulated_camera.devices.pop()
    presenter.camera.device_monitor.videoInputsChanged.emit()
    assert presenter.view.camera_image is None and presenter.slide.camera_image is None
    simulated_camera.devices.append(disconnected)
    presenter.toggle_camera()
    monkeypatch.setattr(qapp, "quit", lambda: None)
    presenter.quit()
    simulated_camera.reply(1)
    assert len(simulated_camera.instances) == 1
    assert not presenter.camera.active and not presenter.camera.requested


def test_camera_appearance_persists_and_is_clamped(qapp, qtbot):
    first = Presenter(qapp)
    first.set_camera_appearance(.55, .35, "top-left")
    second = Presenter(qapp)
    for presenter in (first, second):
        qtbot.addWidget(presenter.presenter)
        qtbot.addWidget(presenter.audience)
        for view in (presenter.view, presenter.slide):
            assert view.camera_width == .55 and view.camera_opacity == .35
            assert view.camera_position == "top-left"
        presenter.session.close()
        presenter.media.close()
    second.set_camera_appearance(7, -1, "invalid")
    assert second.slide.camera_width == .9 and second.slide.camera_opacity == .05
    assert second.slide.camera_position == "bottom-right"
