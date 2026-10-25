from pathlib import Path
import shutil
import subprocess

import pytest
from PySide6.QtCore import QSize

from pagecue.animation import AnimationSpec, AnimationState, timing
from pagecue.document import load_snapshot
from pagecue.session import Session
from pagecue.canvas import Canvas


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


def test_timing_does_not_execute_expressions():
    with pytest.raises(ValueError):
        timing("a0_fps=__import__('os').system('echo forbidden');", 0)
    with pytest.raises(ValueError):
        timing("a0_fps=condition ? doSomething() : 10;", 0)


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


@pytest.fixture(params=["current", "2018"])
def latex_animation(tmp_path, request):
    if request.param == "2018":
        return Path(__file__).parent / "fixtures/generated/animation-2018.pdf"
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
    assert (spec.fps, spec.autoplay, spec.loop, spec.palindrome) == (4, True, True, True)
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
