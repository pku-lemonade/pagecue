"""Snapshot the third-party license pages published with Qt WebEngine's documentation."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from html.parser import HTMLParser
from html import unescape
import json
from pathlib import Path
import re
from urllib.parse import urljoin, urlsplit
from urllib.request import urlopen


class LicensePage(HTMLParser):
    def __init__(self, content):
        super().__init__(convert_charrefs=True)
        self.links = set()
        self.title, self.body = [], []
        self.in_title = False
        self.description_depth = 0
        self.ignored = None
        self.feed(content)

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if tag == "a" and re.search(r"qtwebengine-3rdparty-[^/]+\.html$", attributes.get("href", "")):
            self.links.add(attributes["href"])
        if tag == "h1":
            self.in_title = True
        if tag == "div":
            if self.description_depth:
                self.description_depth += 1
            elif "descr" in attributes.get("class", "").split():
                self.description_depth = 1
        if tag in ("script", "style"):
            self.ignored = tag
        if self.description_depth and tag in ("p", "pre", "br", "li", "h2", "h3"):
            self.body.append("\n")

    def handle_endtag(self, tag):
        if tag == "h1":
            self.in_title = False
        if tag == "div" and self.description_depth:
            self.description_depth -= 1
        if tag == self.ignored:
            self.ignored = None

    def handle_data(self, data):
        if self.ignored:
            return
        if self.in_title:
            self.title.append(data)
        if self.description_depth:
            self.body.append(data)


def collect(base, version, cache):
    cache.mkdir(parents=True, exist_ok=True)
    def fetch(url):
        path = cache / Path(urlsplit(url).path).name
        if not path.exists():
            with urlopen(url, timeout=60) as response:
                content = response.read()
            path.write_bytes(content)
        content = path.read_bytes()
        if f"Qt WebEngine {version}" not in content.decode("utf-8"):
            raise ValueError(f"Unexpected documentation version at {url}")
        return LicensePage(content.decode("utf-8")), hashlib.sha256(content).hexdigest()
    index, digest = fetch(base)
    urls = sorted({urljoin(base, link) for link in index.links})
    if not urls or any(urlsplit(url).netloc != urlsplit(base).netloc for url in urls):
        raise ValueError("Expected third-party license pages on the Qt documentation host")
    def entry(url):
        document, digest = fetch(url)
        title = unescape("".join(document.title)).strip()
        text = unescape("".join(document.body)).strip()
        if not title or not text:
            raise ValueError(f"Missing title or license content: {url}")
        name = Path(urlsplit(url).path).with_suffix(".txt").name
        return name, title, text, {"url": url, "html_sha256": digest}
    with ThreadPoolExecutor(max_workers=4) as workers:
        entries = list(workers.map(entry, urls))
    return {"module": "qtwebengine", "version": version, "source_url": base,
            "index_sha256": digest,
            "source_repository": f"https://code.qt.io/cgit/qt/qtwebengine.git/?h={version}",
            "scope": "Qt's published third-party licensing documentation for this WebEngine version.",
            "components": [{"source_path": origin["url"], "attribution": {"Name": title},
                            "text_files": [name]} for name, title, text, origin in entries],
            "texts": {name: text for name, title, text, origin in entries},
            "text_sources": {name: origin for name, title, text, origin in entries}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="https://doc-snapshots.qt.io/qtwebengine/qtwebengine-licensing.html")
    parser.add_argument("--version", default="6.140.0")
    parser.add_argument("--cache", type=Path, default=Path("build/webengine-license-pages"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = collect(args.url, args.version, args.cache)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Collected {len(result['components'])} license pages into {args.output}")


if __name__ == "__main__":
    main()
