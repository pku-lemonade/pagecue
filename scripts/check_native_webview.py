"""Probe native browser video support before changing the app's WebEngine backend."""

import argparse
import json
import os
from pathlib import Path
import shutil
import sys

# QWebView otherwise prefers WebEngine when both plugins are installed.
os.environ["QT_WEBVIEW_PLUGIN"] = "native"

from PySide6.QtCore import QLibraryInfo, QPluginLoader, QPoint, QSettings, QTimer, QUrl, Qt, qVersion
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtWebView import QWebView, QWebViewLoadingInfo, QWebViewSettings, QtWebView

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = """JSON.stringify((() => {
    const video = document.querySelector('video');
    return {time: video.currentTime, paused: video.paused, ready: video.readyState,
            error: video.error?.message || null, frames: window.presentedFrames || 0,
            userAgent: navigator.userAgent,
            mp4: video.canPlayType('video/mp4; codecs="avc1.42E01E"')};
})())"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "qa/native-webview")
    parser.add_argument("--capture", action="store_true", help="Capture the probe on an unlocked test desktop")
    parser.add_argument("--camera-overlay", action="store_true", help="Use the app's translucent overlay with a synthetic image")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "tests/fixtures/generated/colors.mp4", output / "colors.mp4")
    (output / "player.html").write_text('''<!doctype html><title>Native browser video probe</title>
<body style="background:#222;color:white;font:24px sans-serif"><h1>Original video fixture</h1>
<video id="video" controls autoplay muted loop width="640" src="colors.mp4"></video></body>''')
    QtWebView.initialize()
    app = QApplication([])
    app.setApplicationName("PresenteriyakiNativeBrowserProbe")
    window = QWidget()
    window.setWindowTitle("Presenteriyaki native browser video probe")
    window.resize(800, 600)
    web = QWebView()
    web.settings().setAttribute(QWebViewSettings.WebAttribute.AllowFileAccess, True)
    if sys.platform == "darwin":
        web.settings().setAttribute(QWebViewSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
    container = QWidget.createWindowContainer(web, window)
    container.setGeometry(0, 0, 800, 600)
    if args.camera_overlay:
        from presenteriyaki.canvas import Canvas, WebCameraOverlay
        from presenteriyaki.session import Session
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(output / "settings"))
        session = Session()
        canvas = Canvas(session, False, window)
        canvas.hide()
        canvas.camera_image = QImage(160, 90, QImage.Format.Format_RGB32)
        canvas.camera_image.fill(QColor("#00ff00"))
        overlay = WebCameraOverlay(canvas, window)
        overlay.setGeometry(0, 0, 800, 600)
    else:
        overlay = QWidget(window)
        overlay.setStyleSheet("background: #00ff00")
        overlay.setGeometry(500, 330, 150, 90)
    overlay.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)
    overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    overlay.show()
    overlay.raise_()
    plugin_dir = Path(QLibraryInfo.path(QLibraryInfo.PluginsPath)) / "webview"
    result = {"qt": qVersion(), "samples": [], "passed": False,
              "plugins": {p.name: QPluginLoader(str(p)).metaData() for p in plugin_dir.iterdir()}}
    done = False

    def finish(error=None):
        nonlocal done
        if done:
            return
        done = True
        result["passed"] = error is None
        if error:
            result["error"] = error
        if args.capture:
            origin = window.mapToGlobal(QPoint(0, 0)) - window.screen().geometry().topLeft()
            capture = window.screen().grabWindow(0, origin.x(), origin.y(), window.width(), window.height())
            result["capture_saved"] = capture.save(str(output / "window.png"))
            if not capture.isNull():
                image = capture.toImage()
                scale = capture.devicePixelRatio()
                x, y = (700, 550) if args.camera_overlay else (550, 350)
                result["overlay_pixel"] = image.pixelColor(round(x * scale), round(y * scale)).name()
                result["background_pixel"] = image.pixelColor(round(20 * scale), round(560 * scale)).name()
        (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        app.quit()

    def sample():
        def received(value):
            if done:
                return
            try:
                state = json.loads(value)
            except (TypeError, ValueError) as error:
                finish(f"Invalid browser sample: {error}")
                return
            result["samples"].append(state)
            if state["error"]:
                finish(state["error"])
            elif len(result["samples"]) == 1:
                QTimer.singleShot(1000, sample)
            else:
                first, last = result["samples"]
                advancing = 0 < first["frames"] < last["frames"]
                playing = all(not s["paused"] and s["ready"] >= 2 for s in (first, last))
                finish(None if advancing and playing else "Video frames did not advance")
        web.runJavaScript(SAMPLE, received)

    def loaded(info):
        if info.status() == QWebViewLoadingInfo.LoadStatus.Failed:
            finish(info.errorString())
        elif info.status() == QWebViewLoadingInfo.LoadStatus.Succeeded:
            web.runJavaScript("""window.presentedFrames = 0;
                const video = document.querySelector('video');
                const frame = () => { window.presentedFrames++;
                    video.requestVideoFrameCallback(frame); };
                video.requestVideoFrameCallback(frame); video.play();""", lambda _: None)
            QTimer.singleShot(2000, sample)

    web.loadingChanged.connect(loaded)
    window.show()
    window.raise_()
    window.activateWindow()
    web.setUrl(QUrl.fromLocalFile(str(output / "player.html")))
    QTimer.singleShot(20000, lambda: finish("Native browser probe timed out"))
    app.exec()
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
