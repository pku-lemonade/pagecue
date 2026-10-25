"""Exercise Qt file-opening routes and persistence with isolated preferences.

The picker check uses Qt's widget dialog. It does not claim native OS-dialog or
LaunchServices/Explorer event-delivery verification.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

from PySide6.QtCore import QMimeData, QPoint, QPointF, QSettings, Qt, QTimer, QUrl
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QFileOpenEvent
from PySide6.QtWidgets import QFileDialog

from pagecue.app import Application, Presenter
from pagecue.session import Session


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    original = args.pdf.resolve()
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    paths = {}
    for name in ("drop", "file-event", "picker"):
        path = output / f"{name} 讲稿.pdf"
        shutil.copyfile(original, path)
        paths[name] = path
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(output / "settings"))
    Application.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
    app = Application([])
    presenter = Presenter(app)
    presenter.show()
    results = {"passed": False, "picker_backend": "Qt widget dialog", "file_event_delivery": "QFileOpenEvent via QApplication"}
    def finish(error=None):
        if error:
            results["error"] = str(error)
        (output / "result.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        presenter.quit()
    def exercise():
        assert presenter.open(original)
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(paths["drop"]))])
        enter = QDragEnterEvent(QPoint(50, 50), Qt.DropAction.CopyAction, mime,
                                Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        app.sendEvent(presenter.view, enter)
        assert enter.isAccepted(), "PDF drag was not accepted"
        drop = QDropEvent(QPointF(50, 50), Qt.DropAction.CopyAction, mime,
                         Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        app.sendEvent(presenter.view, drop)
        assert drop.isAccepted() and presenter.session.snapshot.path == paths["drop"]
        results["drop"] = True
        app.sendEvent(app, QFileOpenEvent(str(paths["file-event"])))
        assert presenter.session.snapshot.path == paths["file-event"], "File-open event did not load the PDF"
        results["file_event"] = True
        original_picker = QFileDialog.getOpenFileName
        def widget_picker(parent, caption, directory, filters):
            # Use QFileDialog's documented initial-file selection. Calling
            # selectFile after showing can leave the focused filename editor
            # unchanged, so it is not a reliable simulated user selection.
            selected = original_picker(parent, caption, str(paths["picker"]), filters,
                                       options=QFileDialog.Option.DontUseNativeDialog)
            results["picker_returned"] = selected[0]
            return selected
        QFileDialog.getOpenFileName = widget_picker
        def select_file():
            dialog = next((widget for widget in app.topLevelWidgets()
                           if isinstance(widget, QFileDialog) and widget.isVisible()), None)
            if dialog is not None:
                # QFileSystemModel loads directories asynchronously. Do not
                # accept until the dialog actually reports the intended file.
                QTimer.singleShot(150, lambda: accept_selection(dialog))
            else:
                results["picker_windows"] = [(widget.metaObject().className(), widget.isVisible())
                                             for widget in app.topLevelWidgets()]
                QTimer.singleShot(50, select_file)
        def accept_selection(dialog):
            selected = dialog.selectedFiles()
            results["picker_selected"] = selected
            if selected and Path(selected[0]).resolve() == paths["picker"]:
                dialog.grab().save(str(output / "picker.png"))
                dialog.accept()
            else:
                QTimer.singleShot(100, select_file)
        try:
            QTimer.singleShot(100, select_file)
            presenter.pick()
        finally:
            QFileDialog.getOpenFileName = original_picker
        assert presenter.session.snapshot.path == paths["picker"], "Picker did not load the selected PDF"
        results["picker"] = True
        page = min(2, presenter.session.navigation.count - 1)
        presenter.session.go(page)
        presenter.session.save()
        restored = Session()
        try:
            restored.open(paths["picker"])
            assert restored.page == page, "Saved physical page was not restored"
            restored.open(paths["picker"], page=0)
            assert restored.page == 0, "Explicit initial page did not override the saved page"
        finally:
            restored.close()
        results["recent_page"] = True
        assert hashlib.sha256(original.read_bytes()).hexdigest() == before
        results["source_unchanged"] = True
        results["passed"] = True
        finish()
    def guarded():
        try:
            exercise()
        except Exception as error:
            finish(error)
    def timeout():
        dialog = app.activeModalWidget()
        if isinstance(dialog, QFileDialog):
            dialog.reject()
        finish("File-opening checks timed out")
    QTimer.singleShot(20000, timeout)
    QTimer.singleShot(0, guarded)
    app.exec()
    if not results["passed"]:
        raise SystemExit(1)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
