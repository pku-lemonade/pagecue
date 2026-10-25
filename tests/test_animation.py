from pathlib import Path
import shutil
import subprocess

import pytest
from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtTest import QTest
from pypdf import PdfReader, PdfWriter

from pagecue.animation import AnimationSpec, AnimationState, timing
from pagecue.document import load_snapshot
from pagecue.session import Session
from pagecue.canvas import Canvas
from pagecue.app import Presenter


def pixel_at(view, point):
    capture = view.grab()
    scale = capture.devicePixelRatio()
    return capture.toImage().pixelColor(round(point.x() * scale), round(point.y() * scale))


def test_generated_timing_is_read_without_executing_functions():
    script = """a7_fps=24; a7_playing=false;
    a7_playRight=function(){ a7_playing=true; evil(); };
    a7_gotoNext=function(){ if(a7_playing){ a7_playLeft(); } };
    a7_playRight();"""
    assert timing(script, 7) == (24, True, True, True)
    assert timing(script.replace("a7_playRight();", ""), 7) == (24, False, True, True)


def test_older_object_metadata_and_no_loop():
    script = "a2={dt:1000/8,isPlaying:true,actnNext:function(){ pause(); }};"
    assert timing(script, 2) == (8, True, False, False)
    assert timing("a2.dt=1000/(1e-6+Math.abs(-4));a2.isPlaying=false;", 2)[0] == pytest.approx(4)


def test_timing_does_not_execute_expressions():
    with pytest.raises(ValueError):
        timing("a0_fps=__import__('os').system('echo forbidden');", 0)
    with pytest.raises(ValueError):
        timing("a0_fps=condition ? doSomething() : 10;", 0)
    with pytest.raises(ValueError):
        timing("a0_fps=Math.abs(__import__('os').system('echo forbidden'));", 0)


def test_legacy_constant_frame_rate_expression():
    assert timing("a0_fps=4==0?1e-6:4;a0_playing=false;", 0) == (4, False, False, False)


def test_loop_palindrome_reverse_step_and_speed_controls():
    spec = AnimationSpec(0, 0, (0, 0, 1, 1), [0, 1, 2], fps=4, loop=True, palindrome=True)
    state = AnimationState(spec)
    state.play()
    seen = []
    for _ in range(6):
        seen.append(state.frame)
        state.advance()
    assert seen == [0, 1, 2, 1, 0, 1]
    state.command("EndRight")
    assert state.frame == 2 and state.direction == 0
    state.command("PlayPauseLeft")
    state.advance()
    assert state.frame == 1 and state.direction == -1
    state.command("PlayPauseLeft")
    assert state.direction == 0
    state.command("StepRight")
    assert state.frame == 2
    state.command("Plus")
    assert state.speed > 1
    state.command("Reset")
    assert state.speed == 1
    state.spec.loop = False
    state.direction = 1
    state.advance()
    assert state.direction == 0 and state.frame == 2


def test_space_toggle_pauses_and_resumes_reverse_playback():
    state = AnimationState(AnimationSpec(0, 0, (0, 0, 1, 1), [0, 1, 2]))
    state.command("EndRight")
    state.command("PlayPauseLeft")
    state.command("Toggle")
    assert state.direction == 0
    state.command("Toggle")
    assert state.direction == -1


def test_multiple_animation_posters_controls_and_page_lifecycle(qapp, qtbot, tmp_path):
    path = Path(__file__).parent / "fixtures/generated/multiple-animations.pdf"
    app = Presenter(qapp)
    qtbot.addWidget(app.presenter)
    qtbot.addWidget(app.audience)
    app.show()
    app.open(path)
    assert len(app.session.animations) == 3
    left, right, next_page = app.session.animations.values()
    assert left.frame == 2 and left.direction == 0  # poster=last
    assert right.direction == 1 and right.spec.fps == 7
    assert not next_page.visible  # poster=none
    app.session.animation_command("Pause", right.spec.identifier)
    qtbot.waitUntil(lambda: bool(app.session.images.cache))
    qtbot.waitUntil(lambda: any(key[0] == left.spec.frames[2] for key in app.session.animation_images.cache))
    app.view.repaint()
    poster_point = app.view._from_page(QPointF(left.spec.rect[0] + .01, left.spec.rect[1] + .01)).toPoint()
    color = pixel_at(app.view, poster_point)
    assert color.blue() > 200 and color.red() < 50
    assert app.presenter.grab().save(str(tmp_path / "posters.png"))
    control = next(control for control in left.spec.controls if control.command == "EndLeft")
    point = app.view._from_page(QRectF(*control.rect).center()).toPoint()
    QTest.mouseClick(app.view, Qt.MouseButton.LeftButton, pos=point)
    assert left.frame == 0
    other_frame = right.frame
    QTest.keyClicks(app.view, ">")
    assert left.frame == 1 and right.frame == other_frame
    # Space must pause the selected reverse-playing animation, not switch direction.
    app.session.animation_command("PlayPauseLeft", left.spec.identifier)
    QTest.keyClick(app.view, Qt.Key.Key_Space)
    assert left.direction == 0
    app.session.go(1)
    assert all(not timer.isActive() for timer in app.session.animation_timers.values())
    assert not next_page.visible
    qtbot.waitUntil(lambda: any(key[0] == 1 for key in app.session.images.cache))
    app.view.repaint()
    blank_point = app.view._from_page(QPointF(next_page.spec.rect[0] + .01, next_page.spec.rect[1] + .01)).toPoint()
    color = pixel_at(app.view, blank_point)
    assert min(color.red(), color.green(), color.blue()) > 230
    assert app.audience.grab().save(str(tmp_path / "no-poster.png"))
    center = app.view._from_page(QRectF(*next_page.spec.rect).center()).toPoint()
    QTest.mouseClick(app.view, Qt.MouseButton.LeftButton, pos=center)
    assert next_page.visible and next_page.direction == 1
    app.session.animation_command("Pause", next_page.spec.identifier)
    qtbot.waitUntil(lambda: any(key[0] == next_page.spec.frames[0] for key in app.session.animation_images.cache))
    color = pixel_at(app.view, blank_point)
    # xcolor's cyan is CMYK; PDFium converts it to approximately (0, 174, 239).
    assert color.green() > 150 and color.blue() > 200 and color.red() < 50
    assert app.audience.grab().save(str(tmp_path / "playing.png"))
    app.session.close()
    app.media.close()


def test_merged_animated_decks_keep_distinct_playback_state(qtbot, tmp_path):
    source = Path(__file__).parent / "fixtures/generated/animation.pdf"
    writer = PdfWriter()
    writer.append(PdfReader(source))
    writer.append(PdfReader(source))
    path = tmp_path / "merged.pdf"
    writer.write(path)
    session = Session()
    session.open(path)
    assert len(session.animations) == 2
    first, second = session.animations.values()
    assert (first.spec.page, second.spec.page) == (0, 1)
    assert first.spec.identifier != second.spec.identifier
    session.animation_command("EndRight", first.spec.identifier)
    session.go(1)
    assert second.direction == 1 and first.direction == 0
    assert first.frame == 2 and second.frame == 0
    session.close()


@pytest.fixture(params=["current", "2018", "2016", "2013"])
def latex_animation(tmp_path, request):
    if request.param != "current":
        return Path(__file__).parent / f"fixtures/generated/animation-{request.param}.pdf"
    engine = shutil.which("pdflatex")
    if engine is None:
        path = tmp_path / "animation.pdf"
        shutil.copyfile(Path(__file__).parent / "fixtures/generated/animation.pdf", path)
        return path
    source = Path(__file__).parent / "fixtures/animation.tex"
    result = subprocess.run([engine, "-interaction=nonstopmode", "-halt-on-error",
                             f"-output-directory={tmp_path}", str(source)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout[-3000:]
    return tmp_path / "animation.pdf"


def test_real_latex_frames_metadata_and_qt_rendering(qtbot, latex_animation):
    snapshot = load_snapshot(latex_animation)
    assert not snapshot.notes.diagnostics
    assert len(snapshot.animations) == 1
    spec = snapshot.animations[0]
    assert spec.fps == pytest.approx(4)
    assert (spec.autoplay, spec.loop, spec.palindrome) == (True, True, True)
    assert len(spec.frames) == 3
    assert {c.command for c in spec.controls} >= {"PlayPauseLeft", "PlayPauseRight", "StepRight", "EndLeft"}
    session = Session()
    session.open(latex_animation)
    images = [session.animation_images.document.render(i, QSize(300, 130)) for i in spec.frames]
    colors = [image.pixelColor(10, 10) for image in images]
    assert colors[0].red() > 200 and colors[0].green() < 20
    assert colors[1].green() > 200 and colors[1].red() < 20
    assert colors[2].blue() > 200 and colors[2].red() < 20
    view = Canvas(session, True)
    qtbot.addWidget(view)
    view.resize(1180, 780)
    view.show()
    state = session.animations[0]
    assert session.animation_timers[0].isActive()
    session.animation_command("EndLeft", 0)
    assert not session.animation_timers[0].isActive()
    session.animation_command("StepRight", 0)
    assert state.frame == 1
    qtbot.waitUntil(lambda: any(key[0] == spec.frames[1] for key in session.animation_images.cache), timeout=5000)
    session.tick.stop()
