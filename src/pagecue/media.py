"""Qt media/camera adapters; device access begins only on user request."""

from pathlib import Path
import tempfile
import bisect
from collections import deque

from PySide6.QtCore import QObject, QUrl, Signal, QTimer, Qt
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
        self.frame_start = self.frame_end = None
        self.autoplay = True
        self.gif_delays = []
        self._embedded_paths = {}
        self._step_from = None
        self._step_was_muted = False
        self._step_timeout = QTimer(self)
        self._step_timeout.setSingleShot(True)
        self._step_timeout.timeout.connect(self.pause)
        self.player.mediaStatusChanged.connect(lambda status: self._cancel_step()
            if status == QMediaPlayer.MediaStatus.EndOfMedia else None)

    def _frame(self, frame):
        if frame.isValid():
            self.frame_start = frame.startTime() / 1000
            self.frame_end = frame.endTime() / 1000
            duration = self.frame_end - self.frame_start
            if duration > 0:
                self.frame_duration = duration
            if self._step_from is not None:
                if self.frame_start <= self._step_from:
                    return  # Leave playback running until the next decoded frame.
                self._cancel_step()
                self.player.pause()
            image = frame.toImage()
            if not image.isNull():
                self.frame.emit(image)
                if not self.autoplay:
                    self.player.pause()

    def load(self, media: Media, autoplay=True):
        self.stop()
        self.autoplay = autoplay
        self.frame_start = self.frame_end = None
        self.resource = media
        if media.data is not None:
            # Unique local file; never interpret a PDF attachment filename as a path.
            suffix = Path(media.name.replace("\\", "/")).suffix[:12]
            path = self._embedded_paths.get(media.key)
            if path is None:
                with tempfile.NamedTemporaryFile(dir=self.temp.name, suffix=suffix, delete=False) as stream:
                    stream.write(media.data)
                    path = Path(stream.name)
                self._embedded_paths[media.key] = path
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
            self.gif_delays = []
            for index in range(self.gif.frameCount()):
                self.gif.jumpToFrame(index)
                self.gif_delays.append(max(1, self.gif.nextFrameDelay()))
            self.gif.jumpToFrame(0)
            self.gif.frameChanged.connect(self._gif_frame)
            self.gif.start()
        else:
            self.player.setSource(url)
            self.player.play()

    def _gif_frame(self, index):
        self.frame.emit(self.gif.currentImage())
        self.changed.emit()
        if not self.autoplay:
            self.gif.setPaused(True)

    @property
    def duration(self):
        return sum(self.gif_delays) if self.gif else self.player.duration()

    @property
    def position(self):
        if self.gif:
            return sum(self.gif_delays[:self.gif.currentFrameNumber()])
        if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState and self.frame_start is not None:
            return round(self.frame_start)
        return self.player.position()

    def seek(self, milliseconds):
        if self.gif:
            ends, total = [], 0
            for delay in self.gif_delays:
                total += delay
                ends.append(total)
            self.gif.jumpToFrame(min(max(0, len(ends) - 1), bisect.bisect_right(ends, milliseconds)))
        else:
            self.player.setPosition(max(0, round(milliseconds)))

    def toggle(self):
        self._cancel_step()
        self.autoplay = True
        if self.gif:
            self.gif.setPaused(self.gif.state() == QMovie.MovieState.Running)
        elif self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def pause(self):
        self._cancel_step()
        if self.gif:
            self.gif.setPaused(True)
        self.player.pause()

    def step(self, direction):
        self.pause()
        if self.gif:
            target = min(max(0, self.gif.currentFrameNumber() + direction), max(0, self.gif.frameCount() - 1))
            self.gif.jumpToFrame(target)
        else:
            if direction > 0 and self.frame_start is not None:
                # Packet end timestamps can overlap the final B-frame in VFR
                # video. Decode the actual next frame rather than guessing an FPS.
                self._step_from = self.frame_start
                self._step_was_muted = self.audio.isMuted()
                self.audio.setMuted(True)
                self.autoplay = False
                self.player.setPosition(max(0, round(self.frame_start + 1)))
                self._step_timeout.start(10000)
                self.player.play()
            else:
                target = self.frame_start - 1 if self.frame_start is not None else self.player.position() - self.frame_duration
                self.player.setPosition(max(0, round(target)))

    def _cancel_step(self):
        self._step_timeout.stop()
        if self._step_from is not None:
            self.audio.setMuted(self._step_was_muted)
        self._step_from = None

    def stop(self):
        self._cancel_step()
        self.player.stop()
        if self.gif:
            self.gif.stop()
            self.gif.deleteLater()
            self.gif = None
        self.gif_delays = []

    def close(self):
        self.stop()
        self.player.setSource(QUrl())
        self.temp.cleanup()


class Posters(QObject):
    """Generate small local/embedded media posters sequentially, without audio."""
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.images = {}
        self.queue = deque()
        self.loader = None
        self.generation = 0
        self.timeout = QTimer(self)
        self.timeout.setSingleShot(True)
        self.timeout.timeout.connect(self._finish)
        self.current = None

    def reset(self, resources):
        self.generation += 1
        self.queue.clear()
        self._retire()
        self.images.clear()
        seen = set()
        for resource in resources:
            if resource.url or resource.key in seen:
                continue
            seen.add(resource.key)
            self.queue.append(resource)
        self._next()

    def _retire(self):
        self.timeout.stop()
        if self.loader:
            self.loader.close()
            self.loader.deleteLater()
            self.loader = None
        self.current = None

    def _next(self):
        self._retire()
        if not self.queue:
            return
        self.current = self.queue.popleft()
        key, generation = self.current.key, self.generation
        self.loader = MediaPlayer(self)
        self.loader.audio.setMuted(True)
        self.loader.frame.connect(lambda image: self._receive(generation, key, image))
        self.loader.error.connect(lambda _: self._failed(generation, key))
        self.timeout.start(5000)
        try:
            self.loader.load(self.current, autoplay=False)
        except Exception:
            self._finish()

    def _receive(self, generation, key, image):
        if generation != self.generation or self.current is None or key != self.current.key:
            return
        self.images[key] = image.scaled(400, 300, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        while len(self.images) > 64:
            self.images.pop(next(iter(self.images)))
        self.changed.emit()
        self._finish()

    def _failed(self, generation, key):
        if generation == self.generation and self.current is not None and self.current.key == key:
            self._finish()

    def _finish(self):
        if self.current is None:
            return
        self.current = None
        self.timeout.stop()
        generation = self.generation
        QTimer.singleShot(0, lambda: self._next() if generation == self.generation else None)

    def close(self):
        self.generation += 1
        self.queue.clear()
        self._retire()


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
