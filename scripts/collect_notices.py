"""Collect installed dependency notices and record exact source/version links."""

from importlib.metadata import distribution
import json
from pathlib import Path
import shutil
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/notices"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    names = ("PySide6", "PySide6-Essentials", "PySide6-Addons", "PySide6-Pdf", "PySide6-WebEngine",
             "shiboken6", "pypdf", "cryptography", "cffi", "pycparser", "packaging")
    for name in names:
        installed = distribution(name)
        target = OUT / name
        target.mkdir(exist_ok=True)
        manifest.append({"name": name, "version": installed.version,
                         "license": installed.metadata.get("License-Expression") or installed.metadata.get("License"),
                         "project_urls": installed.metadata.get_all("Project-URL", [])})
        for path in installed.files or []:
            if any(term in str(path).lower() for term in ("license", "copying", "notice")):
                source = Path(installed.locate_file(path))
                if source.is_file():
                    destination = target / str(path).replace("/", "__").replace("\\", "__")
                    shutil.copy2(source, destination)
    # Qt wheels omit standalone license texts; include the terms from the exact
    # upstream release in addition to the package metadata and source directions.
    texts = {
        "LGPL-3.0-only.txt": "https://raw.githubusercontent.com/qt/qtbase/v6.12.0/LICENSES/LGPL-3.0-only.txt",
        "GPL-3.0-only.txt": "https://raw.githubusercontent.com/qt/qtbase/v6.12.0/LICENSES/GPL-3.0-only.txt",
    }
    for name, url in texts.items():
        target = OUT / name
        if not target.exists():
            with urllib.request.urlopen(url, timeout=30) as response:
                target.write_bytes(response.read())
    (OUT / "dependency-versions.json").write_text(json.dumps(manifest, indent=2))
    print("Collected dependency notices:", OUT)


if __name__ == "__main__":
    main()
