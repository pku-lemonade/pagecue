"""Independently implemented format-2 note decoding and precedence."""

from dataclasses import dataclass
import json
from pathlib import Path
from collections.abc import Iterable

LIMIT = 4 * 1024 * 1024


@dataclass(frozen=True)
class Notes:
    pages: dict[int, str]
    source: str | None
    diagnostics: tuple[str, ...] = ()


def decode(data: bytes, count: int) -> tuple[dict[int, str], list[str]]:
    if len(data) > LIMIT:
        raise ValueError("Notes exceed the 4 MiB limit")
    def reject_constant(_):
        raise ValueError("Nonstandard JSON constant")
    try:
        value = json.loads(data.decode("utf-8-sig"), parse_constant=reject_constant)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ValueError("Notes are not valid UTF-8 JSON") from error
    if not isinstance(value, dict) or type(value.get("pdfpcFormat")) is not int or value["pdfpcFormat"] != 2:
        raise ValueError("Expected pdfpcFormat version 2")
    if not isinstance(value.get("pages"), list):
        raise ValueError("Expected a pages array")
    out: dict[int, list[str]] = {}
    problems = []
    for row, entry in enumerate(value["pages"]):
        if not isinstance(entry, dict):
            problems.append(f"Ignored invalid note entry {row}")
            continue
        index, note = entry.get("idx"), entry.get("note", "")
        if type(index) is not int or not 0 <= index < count or not isinstance(note, str):
            problems.append(f"Ignored invalid page/note at entry {row}")
            continue
        try:
            note.encode("utf-8")
        except UnicodeError:
            problems.append(f"Ignored invalid Unicode at entry {row}")
            continue
        if note:
            out.setdefault(index, []).append(note.replace("\r\n", "\n").replace("\r", "\n"))
    return {page: "\n\n".join(parts) for page, parts in out.items()}, problems


def choose(path: Path, count: int, attachments: Iterable[tuple[str, bytes]],
           annotations: dict[int, str]) -> Notes:
    messages: list[str] = []
    selected: dict[int, str] = {}
    source = None
    try:
        for index, (name, data) in enumerate(attachments):
            if index >= 128:
                messages.append("Attachment scan limit reached")
                break
            basename = name.replace("\\", "/").rsplit("/", 1)[-1].lower()
            if not (basename.endswith(".pdfpc") or basename == "speaker-notes.json"):
                continue
            try:
                selected, problems = decode(data, count)
            except ValueError:
                messages.append("Ignored malformed embedded notes")
                continue
            messages.extend(problems)
            source = f"embedded: {name}"
            break
    except Exception:
        messages.append("Could not inspect an embedded notes source")
    if source is None:
        sidecar = path.with_suffix(".pdfpc")
        try:
            with sidecar.open("rb") as stream:
                selected, problems = decode(stream.read(LIMIT + 1), count)
            messages.extend(problems)
            source = str(sidecar)
        except FileNotFoundError:
            pass
        except (OSError, ValueError):
            messages.append("Could not load the adjacent notes file")
    selected.update({page: text for page, text in annotations.items() if text})
    return Notes(selected, source, tuple(messages))
