"""Regenerate the small, original media/LaTeX fixtures for hosts without TeX/FFmpeg."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"
LEGACY_URL = "https://raw.githubusercontent.com/agrahn/animate/0b553a67a44dedc0e8870599b57774461cdf74d3/animate.sty"
LEGACY_SHA256 = "673e073fb2fc4c8c43ea65b2ff0b52e5a190d62989d23da90337b07449ab4763"
ICON_PACKAGES = {
    "animate.sty": {
        "url": "https://raw.githubusercontent.com/agrahn/animate/f24e613ea71dc9031cac4cea69a5dacde8a531c0/animate.sty",
        "sha256": "08b65256f947a7135cab3a295b8f9d8277d7828e1d61950f99597ddc8ffc436a",
    },
    "animfp.sty": {
        "url": "https://raw.githubusercontent.com/yihui/animation/7d22e255c66c754c9b343e755e11eb6e371e5dc5/inst/misc/animate/animfp.sty",
        "sha256": "42b679e70213e830fc7f4a054db339766f05f20303964e05c967e081131a6e26",
    },
}
OLD_WIDGET_PACKAGE = {
    "url": "https://raw.githubusercontent.com/agrahn/animate/d6870ce8f5c4a835e34cf138d5dae7a892950a65/animate.sty",
    "sha256": "311e44ba90a9cdcd89a1cc9c04a893adf217e1d36d91ead9f494dd1ae7a8ec3c",
}


def run(arguments, **options):
    result = subprocess.run(arguments, capture_output=True, text=True, **options)
    if result.returncode:
        raise RuntimeError(result.stdout[-3000:] + result.stderr[-3000:])


def main():
    engine, ffmpeg = shutil.which("pdflatex"), shutil.which("ffmpeg")
    if not engine or not ffmpeg:
        raise SystemExit("Regeneration needs pdflatex with animate/beamer, and ffmpeg with libx264")
    output = FIXTURES / "generated"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        work = Path(directory)
        for name in ("animation", "beamer-notes", "multiple-animations"):
            for _ in range(2):
                run([engine, "-interaction=nonstopmode", "-halt-on-error",
                     f"-output-directory={work}", str(FIXTURES / f"{name}.tex")])
            shutil.copy2(work / f"{name}.pdf", output / f"{name}.pdf")
        # Compile our own source with an unmodified, pinned historic package.
        # The third-party .sty is temporary, not vendored into application code.
        legacy = work / "legacy"
        legacy.mkdir()
        with urllib.request.urlopen(LEGACY_URL, timeout=30) as response:
            package = response.read()
        if hashlib.sha256(package).hexdigest() != LEGACY_SHA256:
            raise RuntimeError("Historic animate package hash mismatch")
        (legacy / "animate.sty").write_bytes(package)
        environment = os.environ.copy()
        environment["TEXINPUTS"] = str(legacy) + os.pathsep
        for _ in range(2):
            run([engine, "-interaction=nonstopmode", "-halt-on-error",
                 f"-output-directory={legacy}", str(FIXTURES / "animation.tex")], env=environment)
        shutil.copy2(legacy / "animation.pdf", output / "animation-2018.pdf")
        icon = work / "icon"
        icon.mkdir()
        for name, metadata in ICON_PACKAGES.items():
            with urllib.request.urlopen(metadata["url"], timeout=30) as response:
                package = response.read()
            if hashlib.sha256(package).hexdigest() != metadata["sha256"]:
                raise RuntimeError(f"Historic {name} hash mismatch")
            (icon / name).write_bytes(package)
        environment["TEXINPUTS"] = str(icon) + os.pathsep
        for _ in range(2):
            run([engine, "-interaction=nonstopmode", "-halt-on-error",
                 f"-output-directory={icon}", str(FIXTURES / "animation.tex")], env=environment)
        shutil.copy2(icon / "animation.pdf", output / "animation-2016.pdf")
        old_widget = work / "widget-2013"
        old_widget.mkdir()
        with urllib.request.urlopen(OLD_WIDGET_PACKAGE["url"], timeout=30) as response:
            package = response.read()
        if hashlib.sha256(package).hexdigest() != OLD_WIDGET_PACKAGE["sha256"]:
            raise RuntimeError("Historic 2013 widget package hash mismatch")
        (old_widget / "animate.sty").write_bytes(package)
        shutil.copy2(icon / "animfp.sty", old_widget / "animfp.sty")
        environment["TEXINPUTS"] = str(old_widget) + os.pathsep
        for _ in range(2):
            run([engine, "-interaction=nonstopmode", "-halt-on-error",
                 f"-output-directory={old_widget}", str(FIXTURES / "animation.tex")], env=environment)
        shutil.copy2(old_widget / "animation.pdf", output / "animation-2013.pdf")
        run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
             "-f", "lavfi", "-i", "color=c=red:s=160x90:r=10:d=1",
             "-f", "lavfi", "-i", "color=c=blue:s=160x90:r=10:d=1",
             "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(output / "colors.mp4")])
        for color in ("red", "green", "blue", "white"):
            Image.new("RGB", (160, 90), color).save(work / f"{color}.png")
        frames = work / "frames.txt"
        frames.write_text("file 'red.png'\nduration 0.12\nfile 'green.png'\nduration 0.52\n"
                          "file 'blue.png'\nduration 0.08\nfile 'white.png'\n", encoding="utf-8")
        run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
             "-i", str(frames), "-fps_mode", "vfr", "-c:v", "libx264", "-pix_fmt", "yuv420p",
             str(output / "vfr.mp4")])
    sources = [Path(__file__), *FIXTURES.glob("*.tex")]
    artifacts = sorted(output.glob("*.pdf")) + sorted(output.glob("*.mp4"))
    manifest = {"historic_package": {"url": LEGACY_URL, "sha256": LEGACY_SHA256, "license": "LPPL"},
                "icon_method_packages": ICON_PACKAGES,
                "old_widget_package": OLD_WIDGET_PACKAGE,
                "tools": {"pdflatex": subprocess.check_output([engine, "--version"], text=True).splitlines()[0],
                          "ffmpeg": subprocess.check_output([ffmpeg, "-version"], text=True).splitlines()[0]},
                "sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                           for path in sources + artifacts}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
