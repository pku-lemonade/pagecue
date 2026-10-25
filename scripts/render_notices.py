"""Create a local, searchable index for bundled dependency notices."""

from html import escape
import hashlib
import json
from urllib.parse import quote


def page(title, body):
    return ("<!doctype html><html lang='en'><meta charset='utf-8'>"
            f"<title>{escape(title)}</title><style>"
            "body{max-width:70em;margin:3em auto;padding:0 1.5em;font:16px/1.5 system-ui}"
            "pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.5 monospace}"
            "section{margin:2em 0}a{overflow-wrap:anywhere}"
            f"</style><main><h1 id='top'>{escape(title)}</h1>{body}</main></html>")


def text_id(name):
    return "text-" + hashlib.sha256(name.encode()).hexdigest()[:16]


def render(root):
    source_pages = []
    for path in sorted((root / "components").glob("*.json")):
        inventory = json.loads(path.read_text(encoding="utf-8"))
        title = f"{inventory['module']} {inventory['version']} — dependency notices"
        source = inventory["source_url"]
        body = [f"<p>Source: <a href='{escape(source, quote=True)}'>{escape(source)}</a></p>",
                f"<p>{escape(inventory['scope'])}</p>", "<h2>Attributions</h2>"]
        if inventory.get("source_repository"):
            repository = escape(inventory["source_repository"], quote=True)
            body.insert(1, f"<p>Library source repository: <a href='{repository}'>{repository}</a></p>")
        for component in inventory["components"]:
            item = component["attribution"]
            copyright = item.get("Copyright", "")
            if isinstance(copyright, list):
                copyright = "\n".join(copyright)
            body.append(f"<h3>{escape(item['Name'])} {escape(item.get('Version', ''))}</h3>"
                        f"<pre>{escape(copyright)}</pre><p>{escape(item.get('License', ''))}</p>")
            body.extend(f"<p><a href='#{text_id(name)}'>{escape(name)}</a></p>" for name in component["text_files"])
        body.append("<h2>License and copyright texts</h2>")
        for name, text in inventory["texts"].items():
            body.append(f"<section id='{text_id(name)}'><h3>{escape(name)}</h3><pre>{escape(text)}</pre>"
                        "<p><a href='#top'>Back to components</a></p></section>")
        if inventory["module"].startswith("qt"):
            body.append("<p>Qt attribution metadata: copyright The Qt Company Ltd.; "
                        "assembled here from the linked upstream notices. License texts are included above.</p>")
        output = path.with_suffix(".html")
        output.write_text(page(title, "\n".join(body)), encoding="utf-8")
        source_pages.append(output)
    body = ["<p>Presenteriyaki includes Python, Qt and other open-source components. "
            "Each retains its own license.</p>"
            "<p><a href='../DISTRIBUTION.md'>Library sources and replacement information</a> · "
            "<a href='native-runtime.json'>Native runtime versions and sources</a></p>"
            "<h2>Component notices</h2><ul>"]
    for path in source_pages:
        relative = path.relative_to(root).as_posix()
        body.append(f"<li><a href='{quote(relative)}'>{escape(path.stem)}</a></li>")
    body.append("</ul><h2>Package and runtime notices</h2><ul>")
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix in (".json", ".html"):
            continue
        relative = path.relative_to(root).as_posix()
        body.append(f"<li><a href='{quote(relative)}'>{escape(relative)}</a></li>")
    body.append("</ul>")
    (root / "index.html").write_text(page("Third-party notices", "\n".join(body)), encoding="utf-8")
