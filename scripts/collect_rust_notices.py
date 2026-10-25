"""Collect registry-crate license files using checksums from an upstream Cargo.lock."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tarfile
import tomllib
from urllib.request import urlopen


def collect(lockfile, cache):
    packages = tomllib.loads(lockfile.read_text(encoding="utf-8"))["package"]
    external = [p for p in packages if p.get("source")]
    if any(not p["source"].startswith("registry+") for p in external):
        raise ValueError("Git dependencies need a separate source/license inventory")
    cache.mkdir(parents=True, exist_ok=True)
    def crate(package):
        name, version = package["name"], package["version"]
        filename = f"{name}-{version}.crate"
        url = f"https://static.crates.io/crates/{name}/{filename}"
        path = cache / filename
        if not path.exists():
            with urlopen(url, timeout=60) as response:
                data = response.read()
            path.write_bytes(data)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != package["checksum"]:
            raise ValueError(f"Cargo checksum mismatch: {filename}")
        texts = {}
        with tarfile.open(fileobj=BytesIO(data), mode="r:gz") as source:
            for item in source:
                leaf = Path(item.name).name.upper()
                if item.isfile() and leaf.startswith(("LICENSE", "COPYING", "NOTICE")):
                    texts[item.name.split("/", 1)[1]] = source.extractfile(item).read().decode("utf-8")
        if not texts:
            raise ValueError(f"No license files found in {filename}")
        return {"name": name, "version": version, "source_url": url,
                "sha256": digest, "texts": texts}
    with ThreadPoolExecutor(max_workers=4) as workers:
        crates = list(workers.map(crate, external))
    return {"lock_sha256": hashlib.sha256(lockfile.read_bytes()).hexdigest(),
            "scope": "Upstream Cargo.lock registry dependencies, including build-time and platform-specific crates.",
            "crates": crates}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lockfile", type=Path)
    parser.add_argument("--cache", type=Path, default=Path("build/crate-notices"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = collect(args.lockfile, args.cache)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Collected license files for {len(result['crates'])} crates")


if __name__ == "__main__":
    main()
