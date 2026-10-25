"""Build the experimental Windows shortcut bridge against pinned Qt 6.12 sources."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "bundle/native-webview"
BUILD = ROOT / "build/native-webview"


def run(*arguments, **options):
    subprocess.run([str(a) for a in arguments], check=True, **options)


def main():
    if sys.platform != "win32":
        raise SystemExit("Build this plugin on Windows x64 with Visual Studio 2022.")
    BUILD.mkdir(parents=True, exist_ok=True)
    sources = json.loads((CONFIG / "sources.json").read_text())
    archives = {}
    for name, source in sources.items():
        archive = BUILD / (name + ".archive")
        if not archive.exists():
            print(f"Downloading {name}", flush=True)
            with urllib.request.urlopen(source["url"], timeout=120) as response, archive.open("wb") as target:
                shutil.copyfileobj(response, target)
        with archive.open("rb") as downloaded:
            digest = hashlib.file_digest(downloaded, "sha256").hexdigest()
        if digest != source["sha256"]:
            raise RuntimeError(f"SHA-256 mismatch for {name}")
        archives[name] = archive
    sdk = BUILD / "sdk"
    for name in ("qtbase", "qtwebview"):
        run("7z", "x", "-y", f"-o{sdk}", archives[name], stdout=subprocess.DEVNULL)
    source_dir = BUILD / "source"
    source_dir.mkdir(exist_ok=True)
    with tarfile.open(archives["source"]) as archive:
        archive.extractall(source_dir, filter="data")
    source_root = next(p for p in source_dir.iterdir() if p.is_dir())
    run("git", "init", "-q", source_root)
    run("git", "apply", CONFIG / "shortcuts.patch", cwd=source_root)
    webview_sdk = BUILD / "webview2"
    with zipfile.ZipFile(archives["webview2"]) as archive:
        archive.extractall(webview_sdk)
    qt_sdk = sdk / "6.12.0/msvc2022_64"
    run("cmake", "-S", CONFIG, "-B", BUILD / "cmake", "-G", "Visual Studio 17 2022", "-A", "x64",
        f"-DCMAKE_PREFIX_PATH={qt_sdk}", f"-DQT_SOURCE_DIR={source_root}", f"-DWEBVIEW2_SDK_ROOT={webview_sdk}")
    run("cmake", "--build", BUILD / "cmake", "--config", "Release", "--parallel", "2")
    plugin = BUILD / "plugins/webview/qtwebview_webview2.dll"
    with plugin.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    (BUILD / "result.json").write_text(json.dumps({"sources": sources, "plugin_sha256": digest}, indent=2))
    print(plugin)


if __name__ == "__main__":
    main()
