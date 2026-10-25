"""Build the experimental Windows shortcut bridge against pinned Qt 6.12 sources."""

import hashlib
import json
import os
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
        raise SystemExit("Build this plugin on Windows x64 with Visual Studio C++ tools.")
    BUILD.mkdir(parents=True, exist_ok=True)
    vswhere = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft Visual Studio/Installer/vswhere.exe"
    installation = subprocess.check_output([str(vswhere), "-latest", "-products", "*", "-requires",
        "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"], text=True).strip()
    if not installation:
        raise SystemExit("Visual Studio C++ tools were not found.")
    vcvars = Path(installation) / "VC/Auxiliary/Build/vcvarsall.bat"
    environment_script = BUILD / "compiler-env.cmd"
    environment_script.write_text(f'@echo off\ncall "{vcvars}" x64 >nul\nif errorlevel 1 exit /b 1\nset\n')
    environment = subprocess.check_output(["cmd", "/d", "/c", str(environment_script)], text=True)
    compiler_env = dict(os.environ)
    compiler_env.update(line.split("=", 1) for line in environment.splitlines() if "=" in line and not line.startswith("="))
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
    qt_config, = sdk.rglob("Qt6Config.cmake")
    qt_sdk = qt_config.parents[3]
    print(f"Qt SDK: {qt_sdk}", flush=True)
    run("cmake", "-S", CONFIG, "-B", BUILD / "cmake", "-G", "NMake Makefiles", "-DCMAKE_BUILD_TYPE=Release",
        f"-DCMAKE_PREFIX_PATH={qt_sdk}", f"-DQT_SOURCE_DIR={source_root}", f"-DWEBVIEW2_SDK_ROOT={webview_sdk}", env=compiler_env)
    run("cmake", "--build", BUILD / "cmake", env=compiler_env)
    plugin = BUILD / "plugins/webview/qtwebview_webview2.dll"
    with plugin.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    (BUILD / "result.json").write_text(json.dumps({"sources": sources, "plugin_sha256": digest}, indent=2))
    print(plugin)


if __name__ == "__main__":
    main()
