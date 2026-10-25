"""Install and exercise a native bundle, then update and remove the test installation."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from install_app import executable, install, platform_name, uninstall, validate

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    platform = platform_name()
    source = ROOT / "dist" / ("PageCue.app" if platform == "macos" else "PageCue")
    validate(source, platform)
    with tempfile.TemporaryDirectory(prefix="pagecue-安装 with spaces-") as directory:
        work = Path(directory)
        destination = work / source.name
        install(source, destination, platform)
        # Launch from outside the repo without inheriting development import paths.
        environment = os.environ.copy()
        for key in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
            environment.pop(key, None)
        environment["QT_QPA_PLATFORM"] = "cocoa" if platform == "macos" else "windows"
        smoke = output / "runtime"
        report = smoke / "result.json"
        if report.exists():
            report.unlink()  # Never accept an old successful run as current evidence.
        arguments = [str(executable(destination, platform)), str(ROOT / "qa/demo.pdf"),
                     "--smoke-output", str(smoke), "--smoke-media",
                     str(ROOT / "tests/fixtures/generated/colors.mp4"), "--smoke-web"]
        with (output / "runtime.log").open("wb") as log:
            result = subprocess.run(arguments, cwd=work, env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=90)
        if result.returncode:
            raise RuntimeError(f"Packaged executable exited with {result.returncode}; see {output / 'runtime.log'}")
        evidence = json.loads(report.read_text(encoding="utf-8"))
        for name in ("passed", "frozen", "rendered", "navigation_reload", "media_decoded", "web_loaded", "web_escape"):
            if evidence.get(name) is not True:
                raise RuntimeError(f"Packaged check failed: {name}: {evidence}")
        for name in ("presenter", "audience", "media", "web"):
            if not (smoke / f"{name}.png").is_file():
                raise RuntimeError(f"Missing {name} capture")
        install(source, destination, platform)
        validate(destination, platform)
        uninstall(destination, platform)
        if destination.exists() or not source.is_dir() or not (ROOT / "qa/demo.pdf").is_file():
            raise RuntimeError("Installation cleanup did not preserve the expected files")
    (output / "installation.json").write_text(json.dumps({
        "passed": True, "platform": platform, "unicode_path": True,
        "install": True, "update": True, "verify": True, "uninstall": True,
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
