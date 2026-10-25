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
import ssl
import sys
import sysconfig
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/notices"


def fetch_notice(url, destination):
    cache = ROOT / "build/license-cache" / hashlib.sha256(url.encode()).hexdigest()
    if not cache.exists():
        with urllib.request.urlopen(url, timeout=30) as response:
            contents = response.read()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(contents)
    shutil.copyfile(cache, destination)


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
    build_file = Path(sys.base_prefix) / "BUILD"
    if build_file.is_file():
        build = build_file.read_text().strip()
        python["distribution"] = "python-build-standalone"
        python["build"] = build
        python["build_recipe"] = f"https://github.com/astral-sh/python-build-standalone/tree/{build}"
        for component in ("bzip2", "expat", "libffi", "liblzma", "mpdecimal", "zlib"):
            url = f"https://raw.githubusercontent.com/astral-sh/python-build-standalone/{build}/LICENSE.{component}.txt"
            target = python_dir / f"LICENSE.{component}.txt"
            fetch_notice(url, target)
            record(target, url)
    from cryptography.hazmat.backends.openssl.backend import backend
    from cryptography.hazmat.bindings import _rust
    openssl = {}
    for owner, description in (("python", ssl.OPENSSL_VERSION), ("cryptography", backend.openssl_version_text())):
        version = description.split()[1]
        source = f"https://github.com/openssl/openssl/tree/openssl-{version}"
        openssl[owner] = {"version": description, "source": source}
        folder = OUT / f"OpenSSL-{version}"
        folder.mkdir(exist_ok=True)
        url = f"https://raw.githubusercontent.com/openssl/openssl/openssl-{version}/LICENSE.txt"
        target = folder / "LICENSE.txt"
        fetch_notice(url, target)
        record(target, url)
    revisions = sorted({match.decode() for match in re.findall(
        rb"rustc[\\/]([0-9a-f]{40})[\\/]", Path(_rust.__file__).read_bytes())})
    rust = {"source_revisions": revisions}
    for revision in revisions:
        folder = OUT / f"Rust-{revision}"
        folder.mkdir(exist_ok=True)
        for name in ("LICENSE-APACHE", "LICENSE-MIT"):
            url = f"https://raw.githubusercontent.com/rust-lang/rust/{revision}/{name}"
            target = folder / name
            fetch_notice(url, target)
            record(target, url)
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
                      "Presenteriyaki makes no modifications to FFmpeg source; these libraries are supplied by the Qt/PySide wheels.\n"
                      "The runtime's reported license and configuration are recorded in native-runtime.json.\n"
                      "The accompanying COPYING files include upstream's optional license variants; their presence does not select them.\n",
                      encoding="utf-8")
    record(credit, "Presenteriyaki attribution for the supplied FFmpeg libraries")
    (OUT / "native-runtime.json").write_text(json.dumps({"python": python, "openssl": openssl,
        "rust_standard_library": rust, "ffmpeg": ffmpeg, "files": files}, indent=2), encoding="utf-8")


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    from PySide6.QtCore import qVersion
    from PySide6.QtWebEngineCore import qWebEngineVersion
    for path in (ROOT / "bundle/notices").glob("*.json"):
        inventory = json.loads(path.read_text(encoding="utf-8"))
        expected = (distribution("cryptography").version if inventory["module"] == "cryptography-rust"
                    else qWebEngineVersion() if inventory["module"] == "qtwebengine" else qVersion())
        if inventory["version"] != expected:
            raise RuntimeError(f"Refresh {path.name}: installed runtime is {expected}")
    manifest = []
    names = ("PySide6", "PySide6-Essentials", "PySide6-Addons", "PySide6-Pdf", "PySide6-WebEngine",
             "shiboken6", "pypdf", "cryptography", "cffi", "pycparser", "packaging", "PyInstaller")
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
    if sys.platform == "win32":
        target = OUT / "native-webview"
        shutil.copytree(ROOT / "bundle/native-webview", target / "bundle/native-webview")
        (target / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts/build_native_webview.py", target / "scripts")
        for name in ("qtwebview-modified-source.tar.gz", "result.json"):
            shutil.copy2(ROOT / "build/native-webview" / name, target / name)
        shutil.copy2(ROOT / "build/native-webview/webview2/LICENSE.txt", target / "Microsoft-WebView2-SDK-LICENSE.txt")
        shutil.copy2(ROOT / "build/native-webview/webview2/NOTICE.txt", target / "Microsoft-WebView2-SDK-NOTICE.txt")
    shutil.copytree(ROOT / "bundle/notices", OUT / "components")
    (OUT / "dependency-versions.json").write_text(json.dumps(manifest, indent=2))
    from render_notices import render
    render(OUT)
    files = [{"path": path.relative_to(OUT).as_posix(),
              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
             for path in sorted(OUT.rglob("*")) if path.is_file() and path.name != "notice-files.json"]
    (OUT / "notice-files.json").write_text(json.dumps({"files": files}, indent=2), encoding="utf-8")
    print("Collected dependency notices:", OUT)


if __name__ == "__main__":
    main()
