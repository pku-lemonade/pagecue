"""Exercise the app's native browser, zoom and camera across window changes."""

import argparse
import json
from pathlib import Path
import shutil
import sys

from PySide6.QtCore import QElapsedTimer, QPoint, QRect, QSettings, QTimer, Qt
from PySide6.QtGui import QColor, QImage, QWindow
from PySide6.QtTest import QTest

from presenteriyaki.app import Application, Presenter
from presenteriyaki.model import Surface

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deck", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--no-capture", action="store_true", help="Check state/DOM only when the local desktop is locked")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "tests/fixtures/generated/colors.mp4", output / "colors.mp4")
    html = output / "browser.html"
    html.write_text('''<!doctype html><title>Native browser integration</title>
<body style="margin:0;background:#18372b;color:white">
<div id="ruler" style="width:100px;height:20px;background:white"></div>
<video id="video" src="colors.mp4" width="320" controls autoplay muted loop></video>
<script>window.framesPresented=0; const video=document.querySelector('video');
const frame=()=>{framesPresented++;video.requestVideoFrameCallback(frame)};
video.requestVideoFrameCallback(frame);</script></body>''')
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(output / "settings"))
    app = Application([sys.argv[0]])
    p = Presenter(app)
    p.show()
    result = {"passed": False, "captures_checked": not args.no_capture, "native_shortcuts": []}
    app.file_opened.connect(lambda path: result.setdefault("file_events", []).append(path))
    done = False

    def finish(error=None):
        nonlocal done
        if done:
            return
        done = True
        result["passed"] = error is None
        if error:
            result["error"] = error
        p.slide.camera_image = None
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        p.quit()

    def guard(callback):
        if done:
            return
        try:
            callback()
        except Exception as error:
            finish(f"{type(error).__name__}: {error}")

    def later(callback, delay=200):
        QTimer.singleShot(delay, lambda: guard(callback))

    def javascript(expression, callback):
        def received(value):
            guard(lambda: callback(json.loads(value)))
        p.web.page().runJavaScript("JSON.stringify(" + expression + ")", received)

    def capture(name):
        screen = p.audience.screen()
        origin = p.audience.mapToGlobal(QPoint()) - screen.geometry().topLeft()
        pixmap = screen.grabWindow(0, origin.x(), origin.y(), p.audience.width(), p.audience.height())
        assert pixmap.save(str(output / (name + ".png"))), "Could not capture audience window"
        return pixmap.toImage(), pixmap.devicePixelRatio()

    def ruler_check(name, expected):
        if args.no_capture:
            return
        image, ratio = capture(name)
        origin = p.web.mapTo(p.audience, QPoint(0, 5))
        left, y = round(origin.x() * ratio), round(origin.y() * ratio)
        end = left
        while end < image.width() and min(image.pixelColor(end, y).getRgb()[:3]) >= 250:
            end += 1
        width = (end - left) / ratio
        assert abs(width - expected) <= 2, f"Rendered ruler width: {width}, expected {expected}"

    def camera_check(name):
        result[name + "_geometry"] = {
            label: [widget.geometry().x(), widget.geometry().y(), widget.width(), widget.height()]
            for label, widget in (("audience", p.audience), ("browser", p.web),
                                  ("container", p.web.container), ("native", p.web.native),
                                  ("camera", p.web.camera))
        }
        if sys.platform == "darwin":
            import objc
            foreign = p.web.native.findChild(QWindow)
            view = objc.objc_object(c_void_p=int(foreign.winId()))
            result[name + "_native_frame"] = str(view.frame())
            result[name + "_camera_level"] = objc.objc_object(c_void_p=int(p.web.camera.winId())).window().level()
            result[name + "_audience_level"] = view.window().level()
        assert p.web.camera.isVisible(), "Camera disappeared"
        assert p.web.camera.geometry() == QRect(p.web.mapToGlobal(QPoint()), p.web.size()), "Camera did not follow the audience"
        if not args.no_capture:
            point = p.web.mapTo(p.audience, QPoint(p.web.width() - 30, p.web.height() - 30))
            elapsed = QElapsedTimer()
            elapsed.start()
            while True:
                image, ratio = capture(name)
                pixel = image.pixelColor(round(point.x() * ratio), round(point.y() * ratio))
                if abs(pixel.red() - 132) <= 3 and abs(pixel.green() - 92) <= 3 or elapsed.elapsed() > 5000:
                    break
                QTest.qWait(50)
            assert abs(pixel.red() - 132) <= 3 and abs(pixel.green() - 92) <= 3, f"Camera composition: {pixel.name()}"
        result[name] = True

    def ready():
        def received(state):
            result["surface_at_load"] = p.session.surface.name
            result["browser_visible"] = p.web.isVisible()
            result["canvas_visible"] = p.slide.isVisible()
            assert p.session.surface == Surface.WEB, "Presentation returned to slides during web load"
            assert state["error"] is None, state["error"]
            if not state["frames"]:
                later(ready, 100)
                return
            result["initial_video_frames"] = state["frames"]
            result["user_agent"] = state["agent"]
            p.web.setZoomFactor(1.5)
            later(zoomed)
        javascript("({frames:framesPresented,error:video.error?.message||null,agent:navigator.userAgent})", received)

    def zoomed():
        def received(zoom):
            assert zoom == 1.5, f"Web zoom: {zoom}"
            # WebKit reports DOM bounds in CSS pixels even with root zoom.
            # The captured ruler establishes its actual rendered size.
            ruler_check("zoomed", 150)
            p.reset_text_zoom()
            later(reset_zoom)
        javascript("parseFloat(getComputedStyle(document.documentElement).zoom)", received)

    def reset_zoom():
        def received(zoom):
            assert zoom == 1.0, f"Zoom reset: {zoom}"
            ruler_check("zoom-reset", 100)
            result["zoom_reset"] = True
            result["rendered_zoom_reset"] = not args.no_capture
            image = QImage(400, 400, QImage.Format.Format_RGB32)
            image.fill(QColor("#f08030"))
            p.slide.camera_image = image
            p.slide.camera_opacity = .5
            p.session.changed.emit()
            p.audience.resize(800, 500)
            p.audience.move(40, 40)
            p.audience.raise_()
            p.audience.activateWindow()
            later(moved, 500)
        javascript("parseFloat(getComputedStyle(document.documentElement).zoom)", received)

    def moved():
        camera_check("camera_initial")
        p.audience.move(120, 90)
        p.audience.resize(900, 560)
        later(fullscreen)

    def send_key(key):
        if sys.platform == "darwin":
            from check_native_web_keys import CocoaKeys
            sender = CocoaKeys(p.audience, result)
            # This sender is not installed as a filter: BrowserIntegration in the app
            # must deliver the shortcut to Presenter.
            sender.send("\uf708" if key == Qt.Key.Key_F5 else "\x1b", 96 if key == Qt.Key.Key_F5 else 53)
        else:
            # The WebView2 bridge separately verifies delivery of these Qt events.
            QTest.keyClick(p.web.native, key)

    def fullscreen():
        camera_check("camera_moved_resized")
        if not args.no_capture:
            p.presenter.setGeometry(p.audience.geometry())
            p.presenter.raise_()
            p.presenter.activateWindow()
            later(presenter_front, 300)
        else:
            enter_fullscreen()

    def presenter_front():
        with_camera, ratio = capture("presenter-front-camera")
        point = p.web.mapTo(p.audience, QPoint(p.web.width() - 30, p.web.height() - 30))
        color = with_camera.pixelColor(round(point.x() * ratio), round(point.y() * ratio))
        frame = p.slide.camera_image
        p.slide.camera_image = None
        p.session.changed.emit()
        def compare():
            without_camera, ratio = capture("presenter-front")
            background = without_camera.pixelColor(round(point.x() * ratio), round(point.y() * ratio))
            assert color == background, "Audience camera covered the foreground presenter window"
            result["camera_behind_presenter"] = True
            p.slide.camera_image = frame
            p.session.changed.emit()
            p.audience.raise_()
            p.audience.activateWindow()
            later(enter_fullscreen, 300)
        later(compare, 300)

    def enter_fullscreen():
        send_key(Qt.Key.Key_F5)
        later(fullscreen_check, 600)

    def fullscreen_check():
        assert p.fullscreen, "Browser F5 did not enter fullscreen"
        camera_check("camera_fullscreen")
        p.leave_fullscreen()
        p.audience.raise_()
        p.audience.activateWindow()
        later(hidden, 400)

    def hidden():
        camera_check("camera_windowed")
        p.hide_all()
        later(restored)

    def restored():
        assert p.web.camera.isHidden(), "Camera remained visible when windows were minimized"
        result["camera_hidden"] = True
        p.restore_all()
        p.audience.raise_()
        p.audience.activateWindow()
        later(final_video, 500)

    def final_video():
        camera_check("camera_restored")
        def received(frames):
            assert frames > result["initial_video_frames"], "Web video stopped across window changes"
            result["final_video_frames"] = frames
            p.slide.camera_image = None
            p.session.changed.emit()
            assert p.web.camera.isHidden(), "Stopped camera remained visible"
            send_key(Qt.Key.Key_Escape)
            later(escaped, 100)
        javascript("framesPresented", received)

    def escaped():
        assert p.session.surface == Surface.SLIDES and p.web.isHidden(), "Browser Escape did not return to slides"
        assert p.web.camera.isHidden(), "Camera tool window survived leaving the browser"
        result["escape_returns_slides"] = True
        finish()

    def start():
        if not p.open(args.deck.resolve()):
            raise RuntimeError("Could not open test deck")
        p.audience.raise_()
        p.audience.activateWindow()
        p.open_web(str(html))
        p.web.shortcut.connect(lambda key: result["native_shortcuts"].append(key))
        p.web.loadFinished.connect(lambda okay: later(ready) if okay else finish("HTML failed to load"))

    QTimer.singleShot(0, lambda: guard(start))
    QTimer.singleShot(30000, lambda: finish("Browser integration timed out"))
    app.exec()
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
