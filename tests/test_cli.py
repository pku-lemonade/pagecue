"""Real command-line exports must work without initializing a GUI platform."""

from io import BytesIO
import os
import subprocess
import sys

from PIL import Image

from pagecue import __version__


def test_cli_version_and_original_icon_export(tmp_path):
    environment = dict(os.environ, QT_QPA_PLATFORM="invalid-headless-check")
    command = [sys.executable, "-m", "pagecue.app"]
    version = subprocess.run(command + ["-v"], env=environment, check=True, capture_output=True, timeout=20)
    assert version.stdout.decode().strip() == __version__
    exported = subprocess.run(command + ["-i"], env=environment, check=True, capture_output=True, timeout=20)
    image = Image.open(BytesIO(exported.stdout))
    assert image.format == "PNG" and image.size == (256, 256)
    image.load()
    assert image.getpixel((0, 0))[3] == 0
    assert image.getpixel((40, 40))[:3] == (23, 35, 54)
    assert image.getpixel((80, 80))[:3] == (244, 240, 231)
    target = tmp_path / "exported icon 图标.png"
    subprocess.run(command + ["--icon", str(target)], env=environment, check=True, capture_output=True, timeout=20)
    assert target.read_bytes() == exported.stdout
