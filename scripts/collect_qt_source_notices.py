"""Extract Qt's attribution metadata and referenced license texts from a source archive."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import tarfile


def collect(archive, module, version):
    metadata_files, texts, roots = {}, {}, set()
    with tarfile.open(archive, "r|xz") as source:
        for item in source:
            if not item.isfile():
                continue
            root, relative = item.name.split("/", 1)
            roots.add(root)
            if relative.startswith("src/") and relative.endswith("qt_attribution.json"):
                metadata_files[relative] = source.extractfile(item).read().decode("utf-8")
            elif relative.startswith("LICENSES/"):
                texts[relative] = source.extractfile(item).read().decode("utf-8")
    if len(roots) != 1:
        raise ValueError("Expected a single Qt module source tree")
    root = roots.pop()
    components = []
    for relative, contents in sorted(metadata_files.items()):
        # Some upstream copyright strings contain literal newlines.
        metadata = json.loads(contents, strict=False)
        for item in metadata if isinstance(metadata, list) else [metadata]:
            files = []
            for key in ("LicenseFile", "LicenseFiles", "CopyrightFile", "CopyrightFiles"):
                value = item.get(key, [])
                files.extend([value] if isinstance(value, str) else value)
            references = [posixpath.normpath(str(PurePosixPath(relative).parent / name)) for name in files]
            if not item.get("LicenseFile") and not item.get("LicenseFiles"):
                for identifier in re.findall(r"[A-Za-z0-9][A-Za-z0-9.+-]*", item["LicenseId"]):
                    if identifier not in ("AND", "OR", "WITH"):
                        references.append(f"LICENSES/{identifier}.txt")
            components.append({"source_path": relative, "attribution": item, "text_files": references})
    needed = {path for item in components for path in item["text_files"]} - texts.keys()
    # Stream a second pass instead of repeatedly seeking through a compressed archive.
    with tarfile.open(archive, "r|xz") as source:
        for item in source:
            relative = item.name.removeprefix(root + "/")
            if item.isfile() and relative in needed:
                texts[relative] = source.extractfile(item).read().decode("utf-8")
    missing = needed - texts.keys()
    if missing:
        raise ValueError(f"Missing referenced notice text: {sorted(missing)}")
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"module": module, "version": version, "archive": archive.name,
            "archive_sha256": digest,
            "scope": "Source-module attribution inventory; includes components not necessarily shipped by the app.",
            "components": components, "texts": dict(sorted(texts.items()))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--module", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = collect(args.archive, args.module, args.version)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Collected {len(result['components'])} attributions and {len(result['texts'])} texts into {args.output}")


if __name__ == "__main__":
    main()
