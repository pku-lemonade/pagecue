"""Command-line startup, separate from the window controller."""

import argparse
from pathlib import Path
import sys

from PySide6.QtCore import QTimer

from . import __version__, STORAGE_NAME


def main():
    parser = argparse.ArgumentParser(description="Presenteriyaki — minimalist PDF presenter")
    parser.add_argument("pdf", nargs="?", type=Path)
    parser.add_argument("--page", "-p", type=int, default=None, help="Initial physical page (1-based)")
    parser.add_argument("--duration", "-d", type=float, default=0, help="Talk duration in minutes")
    parser.add_argument("--version", "-v", action="version", version=__version__)
    parser.add_argument("--icon", "-i", nargs="?", const="-", metavar="FILE",
                        help="Export Presenteriyaki's PNG icon and exit (default: binary stdout)")
    parser.add_argument("--direct-video", "--youtube", "-y", action="store_true", help="Open YouTube links directly for this session")
    parser.add_argument("--smoke-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--smoke-media", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--smoke-web", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--hardware-output", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--hardware-camera", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--notification-output", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.icon is not None:
        from .artwork import icon_png
        if args.icon == "-":
            output = getattr(sys.stdout, "buffer", None)
            if output is None:
                parser.error("Standard output is unavailable; use --icon FILE.png")
            output.write(icon_png())
            output.flush()
        else:
            try:
                with Path(args.icon).open("xb") as output:
                    output.write(icon_png())
            except OSError as error:
                parser.error(f"Could not export icon: {error}. Choose an unused output filename.")
        return 0
    if args.smoke_output and not args.pdf:
        parser.error("The packaged smoke check requires a PDF")
    if args.hardware_camera and not args.hardware_output:
        parser.error("--hardware-camera requires --hardware-output and explicit user authorization")
    if args.hardware_output and (not args.pdf or args.smoke_output):
        parser.error("The hardware check requires a PDF and cannot run with --smoke-output")
    if args.notification_output and (not args.pdf or args.smoke_output or args.hardware_output):
        parser.error("The notification check requires a PDF and cannot run with other diagnostics")
    if args.smoke_output or args.hardware_output or args.notification_output:
        from PySide6.QtCore import QSettings
        QSettings.setDefaultFormat(QSettings.Format.IniFormat)
        QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                          str((args.smoke_output or args.hardware_output or args.notification_output) / "settings"))
    from .app import Application, Presenter
    app = Application(sys.argv[:1])
    app.setApplicationName(STORAGE_NAME)
    app.setApplicationDisplayName("Presenteriyaki")
    app.setOrganizationName(STORAGE_NAME)
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    presenter = Presenter(app)
    if args.direct_video:
        presenter.video_mode = ""
    presenter.session.clock.duration = max(0, args.duration * 60)
    presenter.show()
    if args.smoke_output:
        from .diagnostics import SmokeCheck
        presenter.smoke = SmokeCheck(presenter, args.smoke_output, args.smoke_media, args.smoke_web)
    if args.hardware_output:
        from .hardware import HardwareCheck
        presenter.hardware_check = HardwareCheck(presenter, args.hardware_output, args.hardware_camera)
    if args.notification_output:
        from .notification_check import NotificationCheck
        presenter.notification_check = NotificationCheck(presenter, args.notification_output)
    if args.pdf:
        QTimer.singleShot(0, lambda: presenter.open(args.pdf, page=args.page - 1 if args.page else None))
    app.aboutToQuit.connect(presenter.quit)
    return app.exec()

