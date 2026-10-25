"""Per-user Windows shell links, without changing associations or script policy."""

import base64
import json
import os
from pathlib import Path
import subprocess
import tempfile

DESCRIPTION = "PageCue PDF presenter (org.pku-lemonade.pagecue)"


def default_shortcut():
    roaming = os.environ.get("APPDATA")
    if not roaming:
        raise ValueError("APPDATA is not set; use --no-shortcut for a portable installation")
    return Path(roaming) / "Microsoft/Windows/Start Menu/Programs/PageCue.lnk"


def _shell_link(path, target=None):
    # Only constant code is evaluated. Paths are passed as environment data, so
    # Unicode, quotes, dollar signs and spaces cannot become PowerShell syntax.
    code = """
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($env:PAGECUE_LINK_PATH)
if ($env:PAGECUE_LINK_WRITE -eq 'yes') {
    $link.TargetPath = $env:PAGECUE_LINK_TARGET
    $link.Arguments = ''
    $link.WorkingDirectory = [System.IO.Path]::GetDirectoryName($env:PAGECUE_LINK_TARGET)
    $link.IconLocation = $env:PAGECUE_LINK_TARGET + ',0'
    $link.Description = $env:PAGECUE_LINK_DESCRIPTION
    $link.Save()
}
@{target=$link.TargetPath; arguments=$link.Arguments; description=$link.Description} | ConvertTo-Json -Compress
"""
    environment = os.environ.copy()
    environment.update(PAGECUE_LINK_PATH=str(path), PAGECUE_LINK_TARGET=str(target or ""),
                       PAGECUE_LINK_WRITE="yes" if target else "no", PAGECUE_LINK_DESCRIPTION=DESCRIPTION)
    result = subprocess.run(["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand",
                             base64.b64encode(code.encode("utf-16-le")).decode("ascii")],
                            env=environment, capture_output=True, text=True, encoding="utf-8", timeout=30)
    if result.returncode:
        raise OSError(f"Windows could not access the shortcut: {result.stderr.strip()}")
    return json.loads(result.stdout.lstrip("\ufeff"))


def verify_shortcut(path, target):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Not a PageCue shortcut: {path}")
    info = _shell_link(path)
    if (os.path.normcase(info["target"]) != os.path.normcase(str(target))
            or info["arguments"] or info["description"] != DESCRIPTION):
        raise ValueError(f"Refusing to replace an unrelated shortcut: {path}")


def check_destination(path, target):
    if path.exists() or path.is_symlink():
        verify_shortcut(path, target)


def create_shortcut(path, target):
    check_destination(path, target)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".pagecue-link-", dir=path.parent) as temporary:
        staged = Path(temporary) / "PageCue.lnk"
        _shell_link(staged, target)
        verify_shortcut(staged, target)
        os.replace(staged, path)


def remove_shortcut(path, target):
    if path.exists() or path.is_symlink():
        verify_shortcut(path, target)
        path.unlink()
