"""Extract Qt's attribution metadata and referenced license texts from a source archive."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import tarfile


def collect(archive, module, version, standard_texts=None):
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
    external_sources = {}
    for reference in sorted(missing):
        if reference.startswith("LICENSES/") and reference in (standard_texts or {}):
            standard = standard_texts[reference]
            if hashlib.sha256(standard["text"].encode("utf-8")).hexdigest() != standard["sha256"]:
                raise ValueError(f"Standard license text hash mismatch: {reference}")
            texts[reference] = standard["text"]
            external_sources[reference] = {key: value for key, value in standard.items() if key != "text"}
    missing -= texts.keys()
    if missing:
        raise ValueError(f"Missing referenced notice text: {sorted(missing)}")
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"module": module, "version": version, "archive": archive.name,
            "archive_sha256": digest,
            "scope": "Source-module attribution inventory; includes components not necessarily shipped by the app.",
            "components": components, "texts": dict(sorted(texts.items())), "external_text_sources": external_sources}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--module", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--standard-texts", type=Path, help="JSON of SPDX license texts and their source URLs/hashes")
    args = parser.parse_args()
    standard_texts = json.loads(args.standard_texts.read_text(encoding="utf-8")) if args.standard_texts else None
    result = collect(args.archive, args.module, args.version, standard_texts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Collected {len(result['components'])} attributions and {len(result['texts'])} texts into {args.output}")


if __name__ == "__main__":
    main()
