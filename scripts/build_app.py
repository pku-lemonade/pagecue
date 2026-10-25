"""Build a standalone native application with a private Python/Qt runtime."""

import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    os.chdir(ROOT)
    (ROOT / "build").mkdir(exist_ok=True)
    from pagecue.artwork import icon_png
    (ROOT / "build/icon.png").write_bytes(icon_png(1024))
    from pagecue import __version__
    (ROOT / "build/bundle-identity.json").write_text(json.dumps({"product": "org.pku-lemonade.pagecue", "version": __version__}))
    subprocess.run([sys.executable, str(ROOT / "scripts/collect_notices.py")], check=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    str(ROOT / "bundle/pagecue.spec")], check=True)
    print("Built", ROOT / "dist" / ("PageCue.app" if sys.platform == "darwin" else "PageCue"))


if __name__ == "__main__":
    main()
