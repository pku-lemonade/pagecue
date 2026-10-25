"""Collect installed dependency notices and record exact source/version links."""

from importlib.metadata import distribution
from contextlib import ExitStack
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sys
import sysconfig
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/notices"


def fetch_notice(url, destination):
    if not destination.exists():
        with urllib.request.urlopen(url, timeout=30) as response:
            contents = response.read()
        destination.write_bytes(contents)


def collect_native_runtime():
    """Inspect the actual wheel libraries, not an assumed FFmpeg version."""
    import PySide6
    root = Path(PySide6.__file__).parent
    files = []
    def record(path, source):
        files.append({"path": path.relative_to(OUT).as_posix(), "source": source,
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    version = platform.python_version()
    python_dir = OUT / f"Python-{version}"
    python_dir.mkdir(exist_ok=True)
    target = python_dir / "LICENSE.txt"
    source_url = f"https://raw.githubusercontent.com/python/cpython/v{version}/LICENSE"
    installed = next((folder / name for folder in (Path(sys.base_prefix), Path(sysconfig.get_path("stdlib")))
                      for name in ("LICENSE.txt", "LICENSE", "LICENSE.rst") if (folder / name).is_file()), None)
    if installed:
        shutil.copy2(installed, target)
    else:
        fetch_notice(source_url, target)
    record(target, "Installed Python runtime license" if installed else source_url)
    python = {"version": version, "source": f"https://github.com/python/cpython/tree/v{version}"}
    def library_path(stem):
        matches = [path for pattern in (f"lib{stem}*.dylib", f"{stem}-*.dll", f"lib{stem}.so*")
                   for path in root.rglob(pattern) if path.is_file()]
        if not matches:
            raise RuntimeError(f"Cannot locate Qt's {stem} library for the notice inventory")
        return min(matches, key=lambda path: (len(path.name), str(path)))
    codec_path, utility_path = library_path("avcodec"), library_path("avutil")
    with ExitStack() as stack:
        if os.name == "nt":
            for folder in {codec_path.parent, utility_path.parent, root}:
                stack.enter_context(os.add_dll_directory(str(folder)))
        codec, utility = ctypes.CDLL(str(codec_path)), ctypes.CDLL(str(utility_path))
        def string(library, name):
            function = getattr(library, name)
            function.argtypes, function.restype = [], ctypes.c_char_p
            return function().decode("utf-8")
        ffmpeg = {"version": string(utility, "av_version_info"),
                  "license": string(codec, "avcodec_license"),
                  "configuration": string(codec, "avcodec_configuration"),
                  "library": codec_path.relative_to(root).as_posix(),
                  "library_sha256": hashlib.sha256(codec_path.read_bytes()).hexdigest()}
    if not re.fullmatch(r"\d+\.\d+(?:\.\d+)?", ffmpeg["version"]):
        raise RuntimeError("A non-release FFmpeg build needs an explicit source/notice mapping")
    tag = "n" + ffmpeg["version"]
    ffmpeg["source"] = f"https://github.com/FFmpeg/FFmpeg/tree/{tag}"
    target_dir = OUT / f"FFmpeg-{ffmpeg['version']}"
    target_dir.mkdir(exist_ok=True)
    for name in ("LICENSE.md", "COPYING.LGPLv2.1", "COPYING.LGPLv3", "COPYING.GPLv2", "COPYING.GPLv3"):
        url = f"https://raw.githubusercontent.com/FFmpeg/FFmpeg/{tag}/{name}"
        destination = target_dir / name
        fetch_notice(url, destination)
        record(destination, url)
    credit = target_dir / "ATTRIBUTION.txt"
    credit.write_text("FFmpeg contains code based in part on the work of the Independent JPEG Group.\n"
                      "PageCue makes no modifications to FFmpeg source; these libraries are supplied by the Qt/PySide wheels.\n"
                      "The runtime's reported license and configuration are recorded in native-runtime.json.\n"
                      "The accompanying COPYING files include upstream's optional license variants; their presence does not select them.\n",
                      encoding="utf-8")
    record(credit, "PageCue attribution for the supplied FFmpeg libraries")
    (OUT / "native-runtime.json").write_text(json.dumps({"python": python, "ffmpeg": ffmpeg, "files": files}, indent=2), encoding="utf-8")


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
        fetch_notice(url, target)
    collect_native_runtime()
    (OUT / "dependency-versions.json").write_text(json.dumps(manifest, indent=2))
    print("Collected dependency notices:", OUT)


if __name__ == "__main__":
    main()
