"""Qt media/camera adapters; device access begins only on user request."""

from pathlib import Path
import tempfile

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QImage, QMovie
from PySide6.QtMultimedia import QAudioOutput, QCamera, QMediaCaptureSession, QMediaDevices, QMediaPlayer, QVideoSink

from .document import Media


class MediaPlayer(QObject):
    frame = Signal(QImage)
    changed = Signal()
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.audio.setVolume(.8)
        self.player.setAudioOutput(self.audio)
        self.sink = QVideoSink(self)
        self.player.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(self._frame)
        self.player.errorOccurred.connect(lambda error, text: self.error.emit(text))
        self.player.positionChanged.connect(lambda _: self.changed.emit())
        self.player.durationChanged.connect(lambda _: self.changed.emit())
        self.player.playbackStateChanged.connect(lambda _: self.changed.emit())
        self.gif = None
        self.resource = None
        self.temp = tempfile.TemporaryDirectory(prefix="pagecue-media-")
        self.frame_duration = 1000 / 30

    def _frame(self, frame):
        if frame.isValid():
            image = frame.toImage()
            if not image.isNull():
                self.frame.emit(image)
            duration = (frame.endTime() - frame.startTime()) / 1000
            if duration > 0:
                self.frame_duration = duration

    def load(self, media: Media):
        self.stop()
        self.resource = media
        if media.data is not None:
            # Unique local file; never interpret a PDF attachment filename as a path.
            suffix = Path(media.name.replace("\\", "/")).suffix[:12]
            with tempfile.NamedTemporaryFile(dir=self.temp.name, suffix=suffix, delete=False) as stream:
                stream.write(media.data)
                path = Path(stream.name)
            url = QUrl.fromLocalFile(str(path))
        elif media.path is not None:
            if not media.path.exists():
                raise FileNotFoundError(f"Media file not found: {media.path.name}")
            url = QUrl.fromLocalFile(str(media.path))
        else:
            url = QUrl(media.url or "")
        if url.isLocalFile() and url.toLocalFile().lower().endswith(".gif"):
            self.gif = QMovie(url.toLocalFile(), parent=self)
            if not self.gif.isValid():
                raise ValueError("Could not decode the GIF")
            self.gif.setCacheMode(QMovie.CacheMode.CacheAll)
            self.gif.frameChanged.connect(lambda _: self.frame.emit(self.gif.currentImage()))
            self.gif.start()
        else:
            self.player.setSource(url)
            self.player.play()

    def toggle(self):
        if self.gif:
            self.gif.setPaused(self.gif.state() == QMovie.MovieState.Running)
        elif self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def pause(self):
        if self.gif:
            self.gif.setPaused(True)
        self.player.pause()

    def step(self, direction):
        self.pause()
        if self.gif:
            target = min(max(0, self.gif.currentFrameNumber() + direction), max(0, self.gif.frameCount() - 1))
            self.gif.jumpToFrame(target)
        else:
            self.player.setPosition(max(0, round(self.player.position() + direction * self.frame_duration)))

    def stop(self):
        self.player.stop()
        if self.gif:
            self.gif.stop()
            self.gif.deleteLater()
            self.gif = None

    def close(self):
        self.stop()
        self.player.setSource(QUrl())
        self.temp.cleanup()


class Camera(QObject):
    frame = Signal(QImage)
    error = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.capture = QMediaCaptureSession(self)
        self.sink = QVideoSink(self)
        self.capture.setVideoSink(self.sink)
        self.sink.videoFrameChanged.connect(self._frame)
        self.camera = None

    @property
    def active(self):
        return self.camera is not None and self.camera.isActive()

    @staticmethod
    def devices():
        return QMediaDevices.videoInputs()

    def start(self, device):
        self.stop()
        if self.camera:
            self.camera.deleteLater()
        self.camera = QCamera(device, self)
        self.camera.errorOccurred.connect(lambda error, text: self.error.emit(text))
        self.capture.setCamera(self.camera)
        self.camera.start()

    def _frame(self, frame):
        if frame.isValid():
            image = frame.toImage()
            if not image.isNull():
                self.frame.emit(image)

    def stop(self):
        if self.camera:
            self.camera.stop()
