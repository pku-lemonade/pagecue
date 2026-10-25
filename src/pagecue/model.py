"""Application state independent of the GUI and PDF backend."""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Callable


class Surface(Enum):
    SLIDES = "slides"
    BLACK = "black"
    BOARD = "board"
    MEDIA = "media"
    WEB = "web"


@dataclass
class TalkClock:
    duration: float = 0
    clock: Callable[[], float] = time.monotonic
    accumulated: float = 0
    started: float | None = None
    show_wall: bool = True

    @property
    def elapsed(self) -> float:
        return self.accumulated + (self.clock() - self.started if self.started is not None else 0)

    def toggle(self) -> None:
        self.show_wall = False
        if self.started is None:
            self.started = self.clock()
        else:
            self.accumulated = self.elapsed
            self.started = None

    def reset(self) -> None:
        self.accumulated = 0
        if self.started is not None:
            self.started = self.clock()

    def text(self) -> str:
        if self.show_wall:
            return time.strftime("%H:%M:%S")
        seconds = self.duration - self.elapsed if self.duration else self.elapsed
        sign = "−" if seconds < 0 else ""
        seconds = int(abs(seconds))
        return f"{sign}{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}"


@dataclass
class Navigation:
    count: int
    labels: list[str]
    sections: list[int] = field(default_factory=list)
    page: int = 0
    past: list[int] = field(default_factory=list)
    future: list[int] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.count < 1:
            raise ValueError("A presentation must contain at least one page")
        if len(self.labels) != self.count:
            raise ValueError("Every physical page must have a label")
        self.page = min(max(0, self.page), self.count - 1)

    @property
    def frames(self) -> list[int]:
        return [i for i in range(self.count) if i == 0 or self.labels[i] != self.labels[i - 1]]

    def overlay_pages(self, page: int) -> range:
        start = page
        while start and self.labels[start - 1] == self.labels[page]:
            start -= 1
        return range(start, page + 1)

    def go(self, page: int) -> bool:
        target = min(max(0, page), self.count - 1)
        if target == self.page:
            return False
        self.past.append(self.page)
        self.page = target
        self.future.clear()
        return True

    def history(self, backwards: bool) -> bool:
        source, destination = (self.past, self.future) if backwards else (self.future, self.past)
        if not source:
            return False
        destination.append(self.page)
        self.page = source.pop()
        return True

    def adjacent(self, direction: int, unit: str = "page") -> bool:
        if unit == "page":
            return self.go(self.page + direction)
        candidates = self.frames if unit == "frame" else sorted(set(self.sections))
        if direction < 0:
            candidates = list(reversed(candidates))
        return self.go(next((p for p in candidates if (p - self.page) * direction > 0), self.page))


@dataclass
class Stroke:
    points: list[tuple[float, float]]
    color: str = "#ffee55"
    width: float = 0.003
    opacity: float = 1


@dataclass
class Ink:
    pages: dict[int, list[Stroke]] = field(default_factory=dict)
    selected: list[Stroke] = field(default_factory=list)

    def add(self, page: int, stroke: Stroke) -> None:
        self.pages.setdefault(page, []).append(stroke)

    def visible(self, pages) -> list[Stroke]:
        return [stroke for page in pages for stroke in self.pages.get(page, [])]

    def erase(self, pages) -> None:
        if self.selected:
            selected_ids = {id(s) for s in self.selected}
            for page in pages:
                self.pages[page] = [s for s in self.pages.get(page, []) if id(s) not in selected_ids]
            self.selected.clear()
        else:
            for page in pages:
                self.pages.pop(page, None)

    def transform_selected(self, dx=0.0, dy=0.0, scale=1.0, center=(0.5, 0.5)) -> None:
        cx, cy = center
        for stroke in self.selected:
            stroke.points = [(cx + (x - cx) * scale + dx, cy + (y - cy) * scale + dy)
                             for x, y in stroke.points]
