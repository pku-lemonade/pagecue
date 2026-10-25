from io import BytesIO
from pathlib import Path
import shutil
import subprocess
import time
import wave

import pytest
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject,
                          NameObject, NumberObject, TextStringObject)
from PySide6.QtTest import QTest

from pagecue.app import Presenter
from pagecue.document import Media, load_snapshot
from pagecue.media import MediaPlayer, Posters


def pdf_object(value):
    if isinstance(value, dict):
        return DictionaryObject({NameObject(key): pdf_object(item) for key, item in value.items()})
    if isinstance(value, list):
        return ArrayObject([pdf_object(item) for item in value])
    if isinstance(value, str):
        return NameObject(value) if value.startswith("/") else TextStringObject(value)
    if isinstance(value, int):
        return NumberObject(value)
    return value


@pytest.fixture
def video(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    path = tmp_path / "colors.mp4"
    if not ffmpeg:
        shutil.copyfile(Path(__file__).parent / "fixtures/generated/colors.mp4", path)
        return path
    result = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=red:s=160x90:r=10:d=1",
        "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10:d=1",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return path


def add_media(deck, video, kind):
    writer = PdfWriter(clone_from=PdfReader(deck))
    stream = DecodedStreamObject()
    stream.set_data(video.read_bytes())
    ref = writer._add_object(stream)
    spec = {"/Type": "/Filespec", "/F": "clip.mp4", "/EF": {"/F": ref}}
    annotation = {"/Type": "/Annot", "/Rect": [192, 216, 576, 432]}
    if kind == "Movie":
        annotation.update({"/Subtype": "/Movie", "/Movie": {"/F": str(video.name)}})
    elif kind == "Rendition":
        annotation.update({"/Subtype": "/Screen", "/AA": {"/PO": {
            "/S": "/Rendition", "/R": {"/S": "/MR", "/C": {"/S": "/MCD", "/D": spec}}}}})
    else:
        annotation.update({"/Subtype": "/RichMedia", "/RichMediaContent": {
            "/Assets": {"/Names": ["clip.mp4", spec]},
            "/Configurations": [{"/Instances": [{"/Params": {"/FlashVars": "source=clip.mp4"}}]}]}})
    writer.add_annotation(0, pdf_object(annotation))
    writer.write(deck)


@pytest.mark.parametrize("kind", ["Movie", "Rendition", "RichMedia"])
def test_pdf_media_extraction_and_real_decoding(qtbot, deck, video, kind):
    add_media(deck, video, kind)
    original = deck.read_bytes()
    snapshot = load_snapshot(deck)
    action = next(a for a in snapshot.pages[0].actions if a.kind == "media")
    assert action.rect == pytest.approx((.2, .2, .4, .4))
    assert deck.read_bytes() == original
    if kind == "Movie":
        assert action.value.path == video
    else:
        assert action.value.data == video.read_bytes()
    player = MediaPlayer()
    player.audio.setMuted(True)
    frames = []
    player.frame.connect(lambda image: frames.append(image.copy()))
    player.load(action.value, autoplay=False)
    qtbot.waitUntil(lambda: bool(frames), timeout=5000)
    assert frames[-1].pixelColor(20, 20).red() > 200
    player.step(1)
    qtbot.waitUntil(lambda: player.frame_start == 100, timeout=5000)
    player.step(-1)
    qtbot.waitUntil(lambda: player.frame_start == 0, timeout=5000)
    frames.clear()
    player.seek(1300)
    qtbot.waitUntil(lambda: any(f.pixelColor(20, 20).blue() > 200 for f in frames), timeout=5000)
    player.close()


def test_media_embedded_rectangle_expand_restore(qapp, qtbot, deck, video):
    add_media(deck, video, "RichMedia")
    app = Presenter(qapp)
    qtbot.addWidget(app.presenter)
    qtbot.addWidget(app.audience)
    app.media.audio.setMuted(True)
    app.show()
    assert app.open(deck)
    action = next(a for a in app.session.snapshot.pages[0].actions if a.kind == "media")
    qtbot.waitUntil(lambda: action.value.key in app.posters.images, timeout=5000)
    app.activate(action)
    qtbot.waitUntil(lambda: app.slide.media_image is not None)
    app.media.pause()
    QTest.qWait(50)
    assert app.slide.media_rect == action.rect
    image = app.slide.grab().toImage()
    assert image.pixelColor(380, 210).red() > 200  # inside the media rectangle
    assert image.pixelColor(50, 400).blue() > image.pixelColor(50, 400).red()  # original blue slide
    app.expand_media()
    assert app.slide.media_rect is None
    image = app.slide.grab().toImage()
    assert image.pixelColor(50, 400).red() > 200
    app.expand_media()
    assert app.slide.media_rect == action.rect
    app.posters.close()
    app.media.close()
    app.session.tick.stop()


def test_audio_is_loaded_by_qt_without_playing_audible_sound(qtbot, tmp_path):
    path = tmp_path / "silence.wav"
    with wave.open(str(path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(b"\0\0" * 8000)
    player = MediaPlayer()
    player.audio.setMuted(True)
    player.load(Media(path.name, path=path))
    qtbot.waitUntil(lambda: player.duration >= 900, timeout=5000)
    qtbot.waitUntil(lambda: player.position > 100, timeout=5000)
    player.pause()
    assert player.player.error().value == 0
    player.close()


def test_paused_load_holds_first_frame_during_delayed_event_processing(qtbot, video):
    player = MediaPlayer()
    player.audio.setMuted(True)
    frames = []
    player.frame.connect(lambda image: frames.append(image.copy()))
    player.load(Media(video.name, path=video), autoplay=False)
    # Reproduce a busy UI/cold decoder while the native media clock can run.
    time.sleep(.4)
    qtbot.waitUntil(lambda: bool(frames), timeout=5000)
    assert player.frame_start == 0
    assert frames[-1].pixelColor(20, 20).red() > 200
    QTest.qWait(200)
    assert player.frame_start == 0
    player.close()


def test_variable_frame_rate_step_includes_final_b_frame(qtbot, tmp_path):
    from PIL import Image
    ffmpeg = shutil.which("ffmpeg")
    path = tmp_path / "vfr.mp4"
    if not ffmpeg:
        shutil.copyfile(Path(__file__).parent / "fixtures/generated/vfr.mp4", path)
    else:
        for color in ("red", "green", "blue", "white"):
            Image.new("RGB", (160, 90), color).save(tmp_path / f"{color}.png")
        frames = tmp_path / "frames.txt"
        frames.write_text("file 'red.png'\nduration 0.12\nfile 'green.png'\nduration 0.52\n"
                          "file 'blue.png'\nduration 0.08\nfile 'white.png'\n")
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
            "-i", str(frames), "-fps_mode", "vfr", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)], check=True)
    player = MediaPlayer()
    player.audio.setMuted(True)
    player.load(Media(path.name, path=path), autoplay=False)
    qtbot.waitUntil(lambda: player.frame_start == 0)
    for timestamp in (120, 640, 720):
        player.step(1)
        qtbot.waitUntil(lambda: player.frame_start == timestamp and player._step_from is None, timeout=3000)
        assert player.position == timestamp
    player.step(-1)
    qtbot.waitUntil(lambda: player.frame_start == 640, timeout=3000)
    assert player.audio.isMuted()
    player.close()
