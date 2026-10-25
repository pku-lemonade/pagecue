"""Nonblocking release checks and optional privacy-video URL routing."""

from dataclasses import dataclass
import json
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

from packaging.version import InvalidVersion, Version
from PySide6.QtCore import QCoreApplication, QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest

from . import __version__

REPOSITORY = "pku-lemonade/presenteriyaki"
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases"
RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
SOURCE_TAGS_API = f"https://api.github.com/repos/{REPOSITORY}/tags?per_page=100"
INSTANCES_API = "https://api.invidious.io/instances.json?sort_by=health"


@dataclass(frozen=True)
class Release:
    version: str
    url: str
    newer: bool
    channel: str = "release"


class HttpError(str):
    def __new__(cls, message, status=None):
        result = super().__new__(cls, message)
        result.status = status
        return result


def parse_release(payload, current):
    if not isinstance(payload, dict) or payload.get("draft") or payload.get("prerelease"):
        raise ValueError("No stable release in this response")
    try:
        tag = str(payload["tag_name"])
        version = Version(tag.removeprefix("v"))
        installed = Version(current)
    except (KeyError, InvalidVersion) as error:
        raise ValueError("The release version is not recognizable") from error
    url = str(payload.get("html_url", RELEASES_URL))
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != "github.com":
        raise ValueError("The release URL is not a GitHub HTTPS page")
    return Release(str(version), url, version > installed)


def parse_source_tags(payload, current):
    """Choose the newest non-prerelease version among the returned source tags."""
    if not isinstance(payload, list):
        raise ValueError("The source version metadata is not a tag list")
    candidates = []
    for tag in payload:
        if not isinstance(tag, dict) or not isinstance(tag.get("name"), str):
            continue
        try:
            version = Version(tag["name"].removeprefix("v"))
        except InvalidVersion:
            continue
        if not version.is_prerelease and not version.is_devrelease:
            candidates.append((version, tag["name"]))
    if not candidates:
        raise ValueError("No versioned source tag is available yet")
    version, name = max(candidates)
    return Release(str(version), f"https://github.com/{REPOSITORY}/tree/{quote(name, safe='')}",
                   version > Version(current), "source")


def video_url(original, proxy):
    """Route only recognized YouTube hosts; retain video/query information."""
    parsed = urlsplit(original)
    if parsed.hostname not in ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be") or not proxy:
        return original
    target = urlsplit(proxy)
    if target.scheme != "https" or not target.netloc or target.username or target.password:
        raise ValueError("Use an HTTPS Invidious instance URL")
    path, query = parsed.path, parsed.query
    if parsed.hostname == "youtu.be":
        path = "/watch"
        query = urlencode([("v", parsed.path.lstrip("/"))] + parse_qsl(parsed.query, keep_blank_values=True))
    return urlunsplit((target.scheme, target.netloc, target.path.rstrip("/") + path, query, parsed.fragment))


class JsonRequests(QObject):
    def __init__(self, parent=None):
        super().__init__(parent if parent is not None else QCoreApplication.instance())
        self.manager = QNetworkAccessManager(self)
        self.pending = set()

    def get(self, url, callback):
        request = QNetworkRequest(QUrl(url))
        request.setRawHeader(b"User-Agent", f"Presenteriyaki/{__version__}".encode())
        request.setRawHeader(b"Accept", b"application/json")
        request.setTransferTimeout(10000)
        reply = self.manager.get(request)
        self.pending.add(reply)
        def complete():
            self.pending.discard(reply)
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            error = None
            payload = None
            if status == 404:
                error = HttpError("The requested metadata was not found", status)
            elif reply.error() != QNetworkReply.NetworkError.NoError:
                error = HttpError(reply.errorString(), status)
            else:
                try:
                    data = bytes(reply.readAll())
                    if len(data) > 2 * 1024 * 1024:
                        raise ValueError("Response is too large")
                    payload = json.loads(data)
                except (ValueError, UnicodeError):
                    error = "The server did not return valid JSON metadata"
            reply.deleteLater()
            callback(payload, error)
        reply.finished.connect(complete)

    def close(self):
        for reply in list(self.pending):
            reply.abort()


class ReleaseChecker(QObject):
    checked = Signal(object, bool)
    failed = Signal(str, bool)

    def __init__(self, parent=None, endpoint=RELEASE_API, current=__version__, tags_endpoint=None):
        # Keep asynchronous network objects alive through deferred reply cleanup.
        super().__init__(parent if parent is not None else QCoreApplication.instance())
        self.requests = JsonRequests(self)
        self.endpoint, self.current = endpoint, current
        self.tags_endpoint = tags_endpoint or (SOURCE_TAGS_API if endpoint == RELEASE_API else None)
        self.busy = False
        self.generation = 0

    def cancel(self):
        self.generation += 1
        self.busy = False
        self.requests.close()

    def check(self, manual=True):
        if self.busy:
            return
        self.busy = True
        self.generation += 1
        generation = self.generation
        def finished(payload, error, source=False):
            if generation != self.generation:
                return
            if not source and getattr(error, "status", None) == 404 and self.tags_endpoint:
                self.requests.get(self.tags_endpoint, lambda payload, error: finished(payload, error, source=True))
                return
            self.busy = False
            if error:
                message = "No published release is available yet" if not source and getattr(error, "status", None) == 404 else str(error)
                self.failed.emit(message, manual)
                return
            try:
                release = parse_source_tags(payload, self.current) if source else parse_release(payload, self.current)
            except ValueError as error:
                self.failed.emit(str(error), manual)
            else:
                self.checked.emit(release, manual)
        self.requests.get(self.endpoint, finished)


class VideoRouter(QObject):
    resolved = Signal(str)
    message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent if parent is not None else QCoreApplication.instance())
        self.requests = JsonRequests(self)
        self.cached_instance = None
        self.generation = 0

    def cancel(self):
        """Invalidate callbacks before aborting, which can emit finished inline."""
        self.generation += 1
        self.requests.close()

    def route(self, url, mode):
        self.cancel()
        generation = self.generation
        if mode != "auto" or urlsplit(url).hostname not in ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"):
            self.resolved.emit(video_url(url, mode if mode != "auto" else ""))
            return
        if self.cached_instance:
            self.resolved.emit(video_url(url, self.cached_instance))
            return
        self.message.emit("Finding an available privacy-video instance…")
        def finished(payload, error):
            if generation != self.generation:
                return
            if not error and isinstance(payload, list):
                for row in payload:
                    if isinstance(row, list) and len(row) == 2 and isinstance(row[1], dict):
                        details = row[1]
                        candidate = details.get("uri", "https://" + str(row[0]))
                        if details.get("api"):
                            try:
                                target = video_url(url, candidate)
                            except (TypeError, ValueError, AttributeError):
                                continue
                            self.cached_instance = candidate
                            self.resolved.emit(target)
                            return
            self.message.emit("No privacy-video instance was available; opening the original link")
            self.resolved.emit(url)
        self.requests.get(INSTANCES_API, finished)
