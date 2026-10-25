"""Build a standalone native application with a private Python/Qt runtime."""

import json
import os
from pathlib import Path
import subprocess
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    os.chdir(ROOT)
    (ROOT / "build").mkdir(exist_ok=True)
    from presenteriyaki.artwork import icon_png
    (ROOT / "build/icon.png").write_bytes(icon_png(1024))
    from presenteriyaki import __version__
    (ROOT / "build/bundle-identity.json").write_text(json.dumps({"product": "org.pku-lemonade.pagecue", "version": __version__}))
    subprocess.run([sys.executable, str(ROOT / "scripts/collect_notices.py")], check=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    str(ROOT / "bundle/presenteriyaki.spec")], check=True)
    if sys.platform == "win32":
        # Existing PageCue shortcuts keep working during an explicit in-place update.
        folder = ROOT / "dist/Presenteriyaki"
        shutil.copy2(folder / "Presenteriyaki.exe", folder / "PageCue.exe")
    from check_payload import check_payload
    bundle = ROOT / "dist" / ("Presenteriyaki.app" if sys.platform == "darwin" else "Presenteriyaki")
    inventory = check_payload(bundle, "macos" if sys.platform == "darwin" else "windows")
    (ROOT / "build/payload.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    print("Built", ROOT / "dist" / ("Presenteriyaki.app" if sys.platform == "darwin" else "Presenteriyaki"))


if __name__ == "__main__":
    main()
