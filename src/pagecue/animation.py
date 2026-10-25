"""LaTeX animate metadata, PDF appearance extraction, and playback state.

The metadata reader recognizes generated declarations; it never executes PDF JS.
Frames are independent PDF pages made from the document's appearance resources.
"""

from dataclasses import dataclass, field
from io import BytesIO
import ast
import math
import operator
import re

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject


@dataclass(frozen=True)
class AnimationControl:
    rect: tuple[float, float, float, float]
    command: str


@dataclass
class AnimationSpec:
    identifier: int
    page: int
    rect: tuple[float, float, float, float]
    frames: list[int]
    fps: float = 10
    autoplay: bool = False
    loop: bool = False
    palindrome: bool = False
    controls: list[AnimationControl] = field(default_factory=list)


@dataclass
class AnimationState:
    spec: AnimationSpec
    frame: int = 0
    direction: int = 0
    speed: float = 1

    def play(self, direction=1):
        if direction > 0 and self.frame == len(self.spec.frames) - 1:
            self.frame = 0
        elif direction < 0 and self.frame == 0:
            self.frame = len(self.spec.frames) - 1
        self.direction = 1 if direction > 0 else -1

    def advance(self):
        if not self.direction:
            return
        target = self.frame + self.direction
        last = len(self.spec.frames) - 1
        if target < 0 or target > last:
            if not self.spec.loop:
                self.direction = 0
                return
            if self.spec.palindrome:
                self.direction = -self.direction
                target = self.frame + self.direction
            else:
                target %= len(self.spec.frames)
        self.frame = min(last, max(0, target))

    def command(self, name):
        if name in ("EndLeft", "EndRight"):
            self.frame = 0 if name == "EndLeft" else len(self.spec.frames) - 1
            self.direction = 0
        elif name in ("StepLeft", "StepRight"):
            self.direction = 0
            self.frame = min(len(self.spec.frames) - 1, max(0, self.frame + (-1 if name == "StepLeft" else 1)))
        elif name.startswith("Pause"):
            self.direction = 0
        elif name.startswith("Play") or name == "Toggle":
            direction = -1 if name.endswith("Left") else 1
            if (name.startswith("PlayPause") or name == "Toggle") and self.direction == direction:
                self.direction = 0
            else:
                self.play(direction)
        elif name == "Plus":
            self.speed = min(16, self.speed * 1.1)
        elif name == "Minus":
            self.speed = max(.0625, self.speed / 1.1)
        elif name == "Reset":
            self.speed = 1


def _object(value):
    return value.get_object() if hasattr(value, "get_object") else value


def _matching_brace(text, start):
    depth, quote, escaped = 0, None, False
    for position in range(start, len(text)):
        char = text[position]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in "\"'`":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return position
    return len(text) - 1


def _number(expression):
    tree = ast.parse(expression.strip(), mode="eval")
    operations = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
    def evaluate(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return float(node.value)
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            return operations[type(node.op)](evaluate(node.left), evaluate(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return evaluate(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        raise ValueError("Not a numeric literal/expression")
    if len(list(ast.walk(tree))) > 32:
        raise ValueError("Expression too complex")
    result = evaluate(tree.body)
    if not math.isfinite(result):
        raise ValueError("Non-finite timing")
    return result


def timing(script, identifier):
    """Read modern generated globals and older per-animation object fields."""
    prefix = f"a{identifier}"
    functions = {}
    spans = []
    pattern = r"([\w.$]+)\s*(?:=|:)\s*function\s*\([^)]*\)\s*\{"
    for match in re.finditer(pattern, script):
        start = match.end() - 1
        end = _matching_brace(script, start)
        functions[match.group(1)] = script[start + 1:end]
        spans.append((start, end))
    top = script
    for start, end in reversed(spans):
        top = top[:start] + "{}" + top[end + 1:]
    match = re.search(rf"\b{prefix}_fps\s*=\s*([^;]+)", top)
    fps = _number(match.group(1)) if match else None
    legacy = re.search(rf"\b{prefix}\s*=\s*\{{", top)
    scope = top[legacy.end():_matching_brace(top, legacy.end() - 1)] if legacy else top
    if fps is None:
        interval = re.search(rf"(?:\b{prefix}\.dt\s*=|\bdt\s*:)\s*([0-9.+*/ ()-]+)", scope)
        if interval:
            fps = 1000 / _number(interval.group(1))
    if fps is None or not 0 < fps <= 240:
        raise ValueError("Unrecognized or out-of-range animation frame rate")
    initial = re.search(rf"\b{prefix}_playing\s*=\s*(true|false|1|0)", top)
    old_initial = re.search(rf"(?:\b{prefix}\.isPlaying\s*=|\bisPlaying\s*:)\s*(true|false|1|0)", scope)
    autoplay = bool((initial and initial.group(1) in ("true", "1")) or
                    (old_initial and old_initial.group(1) in ("true", "1")) or
                    re.search(rf"\b{prefix}_(?:playFwd|playBwd|playRight|playLeft)\s*\(", top))
    next_body = functions.get(prefix + "_gotoNext", functions.get(prefix + ".actnNext", functions.get("actnNext", "")))
    loop = bool(re.search(r"\b(?:\w+_playing|isPlaying|\w+\.isPlaying)\b", next_body))
    palindrome = bool(re.search(r"playLeft|playBwd|playsRight\s*=\s*false", next_body))
    return fps, autoplay, loop, palindrome


def _appearance_page(writer, annotation, rotation):
    appearance = _object(_object(annotation["/AP"])["/N"])
    if not hasattr(appearance, "get_data"):
        appearance = _object(appearance.get(annotation.get("/AS"), next(iter(appearance.values()))))
    bounds = [float(v) for v in appearance["/BBox"]]
    matrix = [float(v) for v in appearance.get("/Matrix", [1, 0, 0, 1, 0, 0])]
    a, b, c, d, e, f = matrix
    corners = [(a*x + c*y + e, b*x + d*y + f)
               for x in (bounds[0], bounds[2]) for y in (bounds[1], bounds[3])]
    left, bottom = min(x for x, y in corners), min(y for x, y in corners)
    width = max(x for x, y in corners) - left
    height = max(y for x, y in corners) - bottom
    rect = [float(v) for v in annotation["/Rect"]]
    target_width, target_height = abs(rect[2] - rect[0]), abs(rect[3] - rect[1])
    if min(width, height, target_width, target_height) <= 0:
        raise ValueError("Empty animation appearance")
    page = writer.add_blank_page(target_width, target_height)
    if rotation:
        page[NameObject("/Rotate")] = NumberObject(rotation)
    form = appearance.clone(writer)
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/XObject"): DictionaryObject({
        NameObject("/Frame"): form.indirect_reference})})
    sx, sy = target_width / width, target_height / height
    content = DecodedStreamObject()
    content.set_data(f"q {sx} 0 0 {sy} {-left*sx} {-bottom*sy} cm /Frame Do Q".encode("ascii"))
    page[NameObject("/Contents")] = writer._add_object(content)
    return len(writer.pages) - 1


def extract(reader, rect_converter):
    """Return animation specs, a PDF containing their frames, and diagnostics."""
    writer = PdfWriter()
    specs, problems = [], []
    for page_index, page in enumerate(reader.pages):
        annotations = [_object(ref) for ref in page.get("/Annots", [])]
        fields = {str(a.get("/T", "")): a for a in annotations}
        for name, container in fields.items():
            match = re.fullmatch(r"anm(\d+)", name)
            if not match:
                continue
            identifier = int(match.group(1))
            candidates = sorted((int(key.split(".")[1]), annotation) for key, annotation in fields.items()
                                if re.fullmatch(rf"{identifier}\.\d+", key))
            if not candidates:
                problems.append(f"Animation {identifier} has no readable widget frames")
                continue
            settings = None
            for owner in [container] + annotations:
                for event in ("/PO", "/PV"):
                    try:
                        action = _object(_object(owner.get("/AA", {})).get(event, {}))
                        script = _object(action.get("/JS", ""))
                        script = script.get_data().decode("utf-8") if hasattr(script, "get_data") else str(script)
                        if len(script) > 1024 * 1024:
                            continue
                        settings = timing(script, identifier)
                        break
                    except (ValueError, KeyError, TypeError, ZeroDivisionError, RecursionError):
                        continue
                if settings:
                    break
            if settings is None:
                fps, autoplay, loop, palindrome = 10.0, False, False, False
                problems.append(f"Animation {identifier}: timing metadata needs manual control")
            else:
                fps, autoplay, loop, palindrome = settings
            frame_pages = []
            try:
                for _, annotation in candidates:
                    frame_pages.append(_appearance_page(writer, annotation, int(page.get("/Rotate", 0))))
            except (ValueError, KeyError, TypeError):
                problems.append(f"Animation {identifier}: could not decode its frame appearances")
                continue
            controls = {}
            for field_name, annotation in fields.items():
                normalized = field_name.removeprefix("btn@").replace("@", ".")
                control = re.fullmatch(rf"{identifier}\.([A-Za-z]+)", normalized)
                if not control or "/Rect" not in annotation:
                    continue
                command = control.group(1)
                if command.startswith("Pause") or command.startswith("Play"):
                    command = "PlayPauseLeft" if command.endswith("Left") else "PlayPauseRight"
                key = tuple(float(v) for v in annotation["/Rect"])
                controls[key] = AnimationControl(rect_converter(page, key), command)
            specs.append(AnimationSpec(identifier, page_index, rect_converter(page, container["/Rect"]),
                frame_pages, fps, autoplay, loop, palindrome, list(controls.values())))
    if not specs:
        return [], None, problems
    output = BytesIO()
    writer.write(output)
    return specs, output.getvalue(), problems
