"""Read a PDF snapshot and presentation metadata without modifying source files."""

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
import mimetypes
from urllib.parse import parse_qs, urlparse, unquote

from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, NameObject

from .notes import Notes, choose


class PasswordRequired(ValueError):
    pass


@dataclass
class Media:
    name: str
    path: Path | None = None
    url: str | None = None
    data: bytes | None = None


@dataclass
class Action:
    rect: tuple[float, float, float, float]
    kind: str
    value: int | str | Media
    title: str = ""


@dataclass
class PageInfo:
    label: str
    size: tuple[float, float]
    duration: float | None = None
    actions: list[Action] = field(default_factory=list)
    notes_crop: bool = False


@dataclass
class Snapshot:
    path: Path
    render_bytes: bytes
    pages: list[PageInfo]
    notes: Notes
    sections: list[int]
    original_bytes: bytes
    password: str = ""


def resolved(value):
    return value.get_object() if hasattr(value, "get_object") else value


def rectangle(page, value) -> tuple[float, float, float, float]:
    """Convert PDF bottom-left coordinates to normalized, rotated top-left space."""
    x0, y0, x1, y1 = (float(v) for v in value)
    box = page.cropbox
    width, height = float(box.width), float(box.height)
    rotation = int(page.get("/Rotate", 0)) % 360
    corners = []
    for x, y in [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]:
        u, v = (x - float(box.left)) / width, 1 - (y - float(box.bottom)) / height
        if rotation == 90:
            u, v = 1 - v, u
        elif rotation == 180:
            u, v = 1 - u, 1 - v
        elif rotation == 270:
            u, v = v, 1 - u
        corners.append((u, v))
    left, top = min(p[0] for p in corners), min(p[1] for p in corners)
    return left, top, max(p[0] for p in corners) - left, max(p[1] for p in corners) - top


def filespec(value, directory: Path) -> Media:
    spec = resolved(value)
    if isinstance(spec, dict):
        name = str(spec.get("/UF", spec.get("/F", "embedded-media")))
        streams = resolved(spec.get("/EF", {}))
        stream = resolved(streams.get("/UF", streams.get("/F")))
        if stream is not None:
            return Media(name, data=stream.get_data())
    else:
        name = str(spec)
    parsed = urlparse(name)
    # A Windows drive letter is not a URL scheme.
    if parsed.scheme in ("http", "https"):
        return Media(name, url=name)
    path = Path(unquote(parsed.path)) if parsed.scheme == "file" else Path(name)
    return Media(name, path=(directory / path).resolve())


def is_media(name: str) -> bool:
    kind = mimetypes.guess_type(urlparse(name).path)[0] or ""
    return kind.startswith(("audio/", "video/")) or kind == "image/gif"


def media_from_annotation(annotation, directory: Path) -> Media | None:
    subtype = annotation.get("/Subtype")
    if subtype == "/Movie":
        return filespec(resolved(annotation["/Movie"])["/F"], directory)
    if subtype == "/RichMedia":
        content = resolved(annotation["/RichMediaContent"])
        assets = resolved(resolved(content["/Assets"])["/Names"])
        preferred = None
        try:
            configuration = resolved(resolved(content["/Configurations"])[0])
            instance = resolved(resolved(configuration["/Instances"])[0])
            variables = resolved(instance["/Params"])["/FlashVars"]
            preferred = parse_qs(str(variables)).get("source", [None])[0]
        except (KeyError, IndexError, TypeError):
            pass
        candidates = [(str(assets[i]), assets[i + 1]) for i in range(0, len(assets) - 1, 2)]
        for name, value in sorted(candidates, key=lambda item: item[0] != preferred):
            if name == preferred or is_media(name):
                return filespec(value, directory)
    if subtype in ("/Screen", "/Widget"):
        actions = resolved(annotation.get("/AA", {}))
        action = resolved(actions.get("/PO", annotation.get("/A", {})))
        if action.get("/S") == "/Rendition":
            rendition = resolved(action["/R"])
            clip = resolved(rendition["/C"])
            return filespec(clip["/D"], directory)
    if subtype == "/FileAttachment":
        value = filespec(annotation["/FS"], directory)
        return value if is_media(value.name) else None
    return None


def load_snapshot(path: Path, password: str = "", notes_layout: str = "auto") -> Snapshot:
    path = path.expanduser().resolve()
    data = path.read_bytes()
    reader = PdfReader(BytesIO(data))
    if reader.is_encrypted and not reader.decrypt(password):
        raise PasswordRequired("This PDF needs a password")
    if not reader.pages:
        raise ValueError("The PDF has no pages")
    labels = reader.page_labels
    refs = {page.indirect_reference.idnum: i for i, page in enumerate(reader.pages)
            if page.indirect_reference is not None}
    named = reader.named_destinations
    def destination(value):
        value = resolved(value)
        if isinstance(value, str):
            dest = named.get(value)
            return reader.get_destination_page_number(dest) if dest is not None else None
        if isinstance(value, (list, ArrayObject)) and value:
            ref = value[0]
            return refs.get(ref.idnum) if hasattr(ref, "idnum") else (int(ref) if isinstance(ref, int) else None)
        return None

    annotation_notes = {}
    beamer_notes = {}
    diagnostics = []
    pages = []
    first = reader.pages[0]
    inferred_split = float(first.cropbox.width) / float(first.cropbox.height) > 7 / 3
    split = notes_layout == "right" or (notes_layout == "auto" and inferred_split)
    for index, page in enumerate(reader.pages):
        box = page.cropbox
        width, height = float(box.width), float(box.height)
        if int(page.get("/Rotate", 0)) % 180:
            width, height = height, width
        duration = page.get("/Dur")
        info = PageInfo(labels[index], (width, height),
                        float(duration) if duration is not None and float(duration) > 0 else None,
                        notes_crop=split)
        text = []
        for ref in page.get("/Annots", []):
            annotation = resolved(ref)
            subtype = annotation.get("/Subtype")
            if subtype == "/Text":
                content = str(annotation.get("/Contents", "")).strip()
                if content:
                    text.append(content.replace("\r", "\n"))
            if "/Rect" not in annotation:
                continue
            rect = rectangle(page, annotation["/Rect"])
            try:
                media = media_from_annotation(annotation, path.parent)
                if media is not None:
                    info.actions.append(Action(rect, "media", media, media.name))
                    continue
            except Exception:
                diagnostics.append(f"Could not read a media annotation on page {index + 1}")
            if subtype != "/Link":
                continue
            action = resolved(annotation.get("/A", {}))
            dest = destination(annotation.get("/Dest", action.get("/D")))
            if dest is not None:
                info.actions.append(Action(rect, "page", dest, f"Go to page {dest + 1}"))
            elif action.get("/S") == "/Named":
                info.actions.append(Action(rect, "named", str(action.get("/N", ""))))
            elif action.get("/S") in ("/URI", "/Launch", "/GoToR"):
                value = str(action.get("/URI", action.get("/F", "")))
                if is_media(value):
                    resource = filespec(value, path.parent)
                    info.actions.append(Action(rect, "media", resource, value))
                else:
                    info.actions.append(Action(rect, "url", value, value))
        if text:
            annotation_notes[index] = "\n\n".join(text)
        if split:
            extracted = []
            def visitor(text, cm, tm, font, size):
                x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
                if x >= float(box.left) + float(box.width) / 2:
                    extracted.append(text)
            try:
                page.extract_text(visitor_text=visitor)
                beamer_notes[index] = "".join(extracted).strip()
            except Exception:
                diagnostics.append(f"Could not extract notes-region text on page {index + 1}")
        pages.append(info)

    def attachments():
        for attachment in reader.attachment_list:
            name = attachment.name or attachment.alternative_name or ""
            if name.lower().endswith(".pdfpc") or name.lower() == "speaker-notes.json":
                yield name, attachment.content
    notes = choose(path, len(pages), attachments(), annotation_notes)
    for page, text in beamer_notes.items():
        if text:
            notes.pages[page] = "\n\n".join(filter(None, [notes.pages.get(page), text]))
    notes = Notes(notes.pages, notes.source, notes.diagnostics + tuple(diagnostics))
    sections = []
    for outline in reader.outline:
        if not isinstance(outline, list):
            number = reader.get_destination_page_number(outline)
            if number is not None and number >= 0:
                sections.append(number)
    # Remove comment annotations from the render-only copy, retaining the source.
    writer = PdfWriter(clone_from=reader)
    for page in writer.pages:
        if "/Annots" in page:
            page[NameObject("/Annots")] = ArrayObject(
                ref for ref in page["/Annots"] if resolved(ref).get("/Subtype") != "/Text")
    target = BytesIO()
    writer.write(target)
    return Snapshot(path, target.getvalue(), pages, notes, sections, data, password)
