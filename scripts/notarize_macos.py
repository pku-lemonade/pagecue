"""Notarize a Developer ID-signed app and produce a stapled disk image."""

import argparse
import json
import subprocess
import sys

from build_installer import ROOT, artifact_path, main as build_installer
from install_app import validate


def submit(path, profile, output):
    result = subprocess.run(["xcrun", "notarytool", "submit", str(path),
        "--keychain-profile", profile, "--wait", "--output-format", "json"],
        capture_output=True, text=True)
    output.write_text(result.stdout, encoding="utf-8")
    if result.returncode:
        raise SystemExit(result.stderr or f"Notarization failed; see {output}")
    report = json.loads(result.stdout)
    if report["status"] != "Accepted":
        subprocess.run(["xcrun", "notarytool", "log", report["id"],
            "--keychain-profile", profile, str(output.with_suffix(".log.json"))], check=True)
        raise SystemExit(f"Apple returned {report['status']}; see {output.with_suffix('.log.json')}")


def staple(path):
    subprocess.run(["xcrun", "stapler", "staple", str(path)], check=True)
    subprocess.run(["xcrun", "stapler", "validate", str(path)], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True, help="Existing notarytool Keychain profile name")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Notarization runs on macOS")
    app = ROOT / "dist/Presenteriyaki.app"
    validate(app, "macos")
    signature = subprocess.run(["codesign", "--display", "--verbose=4", str(app)],
        check=True, capture_output=True, text=True).stderr
    identity = next((line.removeprefix("Authority=") for line in signature.splitlines()
                     if line.startswith("Authority=Developer ID Application:")), None)
    if not identity or "runtime" not in signature or "Timestamp=" not in signature:
        raise SystemExit("Build with PRESENTERIYAKI_CODESIGN_IDENTITY set to a Developer ID Application identity first.")
    output = ROOT / "build/notarization"
    output.mkdir(parents=True, exist_ok=True)
    archive = output / "Presenteriyaki.zip"
    subprocess.run(["ditto", "-c", "-k", "--keepParent", str(app), str(archive)], check=True)
    submit(archive, args.profile, output / "app.json")
    staple(app)
    build_installer()
    image = artifact_path()
    subprocess.run(["codesign", "--force", "--sign", identity, "--timestamp", str(image)], check=True)
    subprocess.run(["codesign", "--verify", "--strict", str(image)], check=True)
    submit(image, args.profile, output / "dmg.json")
    staple(image)
    subprocess.run(["spctl", "--assess", "--type", "execute", "--verbose=2", str(app)], check=True)
    subprocess.run(["spctl", "--assess", "--type", "open", "--context", "context:primary-signature",
                    "--verbose=2", str(image)], check=True)
    print(image)


if __name__ == "__main__":
    main()
