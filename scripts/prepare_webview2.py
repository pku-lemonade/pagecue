"""Fetch and verify Microsoft's pinned WebView2 installer for Windows Setup."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def prepare():
    source = json.loads((ROOT / "bundle/webview2-bootstrapper.json").read_text())
    target = ROOT / "build/MicrosoftEdgeWebview2Setup.exe"
    if not target.exists():
        with urllib.request.urlopen(source["url"], timeout=60) as response, target.open("wb") as output:
            shutil.copyfileobj(response, output)
    if hashlib.sha256(target.read_bytes()).hexdigest() != source["sha256"]:
        raise RuntimeError("WebView2 installer SHA-256 does not match the pinned download")
    script = ("$ErrorActionPreference = 'Stop'; "
              "$s = Get-AuthenticodeSignature -LiteralPath $env:PRESENTERIYAKI_WEBVIEW_SETUP; "
              "@{status=$s.Status.ToString(); subject=$s.SignerCertificate.Subject} | ConvertTo-Json -Compress")
    shell = shutil.which("pwsh") or "powershell"
    signature = json.loads(subprocess.check_output([shell, "-NoProfile", "-NonInteractive", "-Command", script],
        env={**os.environ, "PRESENTERIYAKI_WEBVIEW_SETUP": str(target)}, text=True))
    if signature["status"] != "Valid" or "CN=Microsoft Corporation," not in signature["subject"]:
        raise RuntimeError(f"WebView2 installer signature verification failed: {signature}")
    (ROOT / "build/webview2-bootstrapper.json").write_text(json.dumps({**source, **signature}, indent=2))
    return target
