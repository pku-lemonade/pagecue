"""Regenerate the small, original media/LaTeX fixtures for hosts without TeX/FFmpeg."""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures"


def run(arguments):
    result = subprocess.run(arguments, capture_output=True, text=True)
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
        for name in ("animation", "beamer-notes"):
            for _ in range(2):
                run([engine, "-interaction=nonstopmode", "-halt-on-error",
                     f"-output-directory={work}", str(FIXTURES / f"{name}.tex")])
            shutil.copy2(work / f"{name}.pdf", output / f"{name}.pdf")
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
    manifest = {"tools": {"pdflatex": subprocess.check_output([engine, "--version"], text=True).splitlines()[0],
                          "ffmpeg": subprocess.check_output([ffmpeg, "-version"], text=True).splitlines()[0]},
                "sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                           for path in sources + artifacts}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
