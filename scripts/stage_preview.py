"""Transfer a successful native build to an existing draft GitHub prerelease."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def api(path):
    return json.loads(subprocess.run(["gh", "api", path], check=True, capture_output=True, text=True).stdout)


def validate_source(run, release):
    if not release["draft"] or not release["prerelease"]:
        raise ValueError("Only an existing draft prerelease can receive preview installers")
    if (run["conclusion"] != "success" or run["head_branch"] != "main"
            or run["path"] != ".github/workflows/native.yml"):
        raise ValueError("Select a successful native workflow run from main")
    if release["target_commitish"] != run["head_sha"]:
        raise ValueError("The draft target does not match the tested source commit")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--run", required=True, type=int)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    tag = "v" + args.version
    run = api(f"repos/{args.repo}/actions/runs/{args.run}")
    # The by-tag REST endpoint omits drafts until the Git tag exists.
    releases = api(f"repos/{args.repo}/releases?per_page=100")
    release = next((item for item in releases if item["tag_name"] == tag), None)
    if release is None:
        raise ValueError(f"Create the draft {tag} release first")
    validate_source(run, release)
    output = Path("build/release-assets")
    downloads = output / "downloaded"
    subprocess.run(["gh", "run", "download", str(args.run), "--repo", args.repo,
                    "--pattern", "installer-*", "--dir", str(downloads)], check=True)
    expected = {f"Presenteriyaki-{args.version}-{suffix}" for suffix in
                ("macos-arm64.dmg", "macos-x86_64.dmg", "windows-x64-setup.exe")}
    installers = [path for path in downloads.rglob("*") if path.is_file()]
    if len(installers) != 3 or {path.name for path in installers} != expected:
        raise ValueError(f"Expected exactly the three {args.version} platform installers")
    digests = {}
    for path in installers:
        target = output / path.name
        shutil.copyfile(path, target)
        with target.open("rb") as stream:
            digests[target.name] = hashlib.file_digest(stream, "sha256").hexdigest()
    checksums = output / "SHA256SUMS.txt"
    checksums.write_text("".join(f"{digest}  {name}\n" for name, digest in sorted(digests.items())), encoding="utf-8")
    digests[checksums.name] = hashlib.sha256(checksums.read_bytes()).hexdigest()
    subprocess.run(["gh", "release", "upload", tag, "--repo", args.repo, "--clobber",
                    *(str(output / name) for name in sorted(digests))], check=True)
    uploaded = api(f"repos/{args.repo}/releases/{release['id']}")
    if not uploaded["draft"]:
        raise ValueError("The release was published before staging completed")
    assets = {item["name"]: item for item in uploaded["assets"]}
    for name, digest in digests.items():
        if assets[name]["digest"] != "sha256:" + digest:
            raise ValueError(f"GitHub's uploaded-file digest does not match {name}")
    result = {"passed": True, "source_commit": run["head_sha"], "native_run": args.run,
              "release_id": release["id"], "draft": True, "sha256": digests}
    (output / "verification.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
