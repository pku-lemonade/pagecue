"""Exercise the packaged DMG or Windows Setup artifact."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from build_installer import artifact_path, ROOT
from install_app import validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    output = parser.parse_args().output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    artifact = artifact_path()
    if sys.platform == "win32" and os.environ.get("GITHUB_ACTIONS") != "true":
        raise SystemExit("Run the Windows installer check on a fresh CI runner; it creates an uninstall entry and Start Menu link.")
    with tempfile.TemporaryDirectory(prefix="presenteriyaki-installer-演示-") as temporary:
        work = Path(temporary)
        if sys.platform == "darwin":
            mount = work / "volume"
            mount.mkdir()
            subprocess.run(["hdiutil", "attach", "-nobrowse", "-readonly", "-mountpoint", str(mount), str(artifact)], check=True)
            try:
                assert (mount / "Applications").is_symlink()
                assert os.readlink(mount / "Applications") == "/Applications"
                subprocess.run([sys.executable, str(ROOT / "scripts/check_bundle.py"), "--source",
                    str(mount / "Presenteriyaki.app"), "--output", str(output / "application")], check=True)
            finally:
                subprocess.run(["hdiutil", "detach", str(mount)], check=True)
        else:
            target = work / "Installed App"
            flags = ["/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/NOCLOSEAPPLICATIONS"]
            def install(log):
                subprocess.run([str(artifact), *flags, f"/DIR={target}", f"/LOG={output / log}"], check=True, timeout=180)
            install("install.log")
            try:
                validate(target, "windows")
                runtime = output / "runtime"
                with (output / "runtime.log").open("wb") as log:
                    subprocess.run([str(target / "Presenteriyaki.exe"), str(ROOT / "qa/demo.pdf"),
                        "--smoke-output", str(runtime), "--smoke-web", "--smoke-media",
                        str(ROOT / "tests/fixtures/generated/colors.mp4")], stdout=log,
                        stderr=subprocess.STDOUT, check=True, timeout=90)
                assert json.loads((runtime / "result.json").read_text())["passed"]
                from windows_shortcut import default_shortcut, verify_shortcut
                verify_shortcut(default_shortcut(), target / "Presenteriyaki.exe")
                install("update.log")
                validate(target, "windows")
            finally:
                subprocess.run([str(target / "unins000.exe"), *flags], check=True, timeout=120)
            assert not (target / "Presenteriyaki.exe").exists()
            assert not default_shortcut().exists()
    (output / "result.json").write_text(json.dumps({"passed": True, "artifact": artifact.name,
        "install": True, "launch": True, "update": True, "uninstall": True}, indent=2))


if __name__ == "__main__":
    main()
