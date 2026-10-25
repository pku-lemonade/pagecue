"""Package an existing native build as a Mac disk image or Windows installer."""

import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

from presenteriyaki import __version__
from install_app import validate

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist/installers"


def artifact_path():
    if sys.platform == "darwin":
        return OUTPUT / f"Presenteriyaki-{__version__}-macos-{platform.machine()}.dmg"
    if sys.platform == "win32":
        return OUTPUT / f"Presenteriyaki-{__version__}-windows-x64-setup.exe"
    raise SystemExit("Build installers on macOS or Windows.")


def main():
    output = artifact_path()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        app = ROOT / "dist/Presenteriyaki.app"
        validate(app, "macos")
        with tempfile.TemporaryDirectory(prefix="presenteriyaki-dmg-") as temporary:
            staging = Path(temporary)
            shutil.copytree(app, staging / app.name, symlinks=True)
            (staging / "Applications").symlink_to("/Applications", target_is_directory=True)
            (staging / "Install Presenteriyaki.txt").write_text(
                "Drag Presenteriyaki to Applications, then open it from there.\n"
                "You can also copy it to a folder in your home directory.\n"
                "Close the app before replacing an older version.\n")
            subprocess.run(["hdiutil", "create", "-ov", "-format", "UDZO", "-volname", "Presenteriyaki",
                            "-srcfolder", str(staging), str(output)], check=True)
    else:
        source = ROOT / "dist/Presenteriyaki"
        validate(source, "windows")
        compiler = shutil.which("ISCC") or str(Path(os.environ["ProgramFiles(x86)"]) / "Inno Setup 6/ISCC.exe")
        if not Path(compiler).is_file():
            raise SystemExit("Install Inno Setup 6 from https://jrsoftware.org/isinfo.php, then rerun this command.")
        from prepare_webview2 import prepare
        webview_setup = prepare()
        subprocess.run([compiler, "/Qp", f"/DAppVersion={__version__}", f"/DSourceDir={source}",
                        f"/DWebViewSetup={webview_setup}",
                        f"/O{OUTPUT}", f"/F{output.stem}", str(ROOT / "bundle/windows.iss")], check=True)
    print(output)


if __name__ == "__main__":
    main()
