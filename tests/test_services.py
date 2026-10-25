import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

import pytest

from pagecue.services import ReleaseChecker, VideoRouter, parse_release, video_url


def test_release_versions_and_url_validation():
    payload = {"tag_name": "v0.2.0", "html_url": "https://github.com/pku-lemonade/pagecue/releases/tag/v0.2.0"}
    assert parse_release(payload, "0.1.0").newer
    assert not parse_release(payload, "0.2.1").newer
    with pytest.raises(ValueError):
        parse_release({**payload, "prerelease": True}, "0.1.0")
    with pytest.raises(ValueError):
        parse_release({**payload, "html_url": "file:///tmp/not-an-update"}, "0.1.0")


def test_privacy_routing_preserves_video_and_query():
    assert video_url("https://youtu.be/abc?t=12", "https://video.example") == "https://video.example/watch?v=abc&t=12"
    assert video_url("https://www.youtube.com/watch?v=abc&list=xyz", "https://video.example/") == "https://video.example/watch?v=abc&list=xyz"
    assert video_url("https://unrelated.example/watch?v=abc", "https://video.example") == "https://unrelated.example/watch?v=abc"
    assert video_url("https://www.youtube.com/watch?v=abc", "") == "https://www.youtube.com/watch?v=abc"
    with pytest.raises(ValueError):
        video_url("https://youtu.be/abc", "http://insecure.example")


@pytest.fixture
def release_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/missing":
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"tag_name": "v0.2.0", "html_url": "https://github.com/pku-lemonade/pagecue/releases/tag/v0.2.0"}).encode())
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def test_qt_network_release_check_and_missing_channel(qapp, qtbot, release_server):
    checker = ReleaseChecker(endpoint=release_server + "/latest")
    assert checker.parent() is qapp
    with qtbot.waitSignal(checker.checked, timeout=3000) as signal:
        checker.check(manual=True)
    assert signal.args[0].version == "0.2.0"
    assert signal.args[1] is True
    checker.endpoint = release_server + "/missing"
    with qtbot.waitSignal(checker.failed, timeout=3000) as signal:
        checker.check(manual=False)
    assert "No published release" in signal.args[0]
    assert signal.args[1] is False


def test_automatic_instance_resolution_and_stale_response(qtbot, monkeypatch):
    router = VideoRouter()
    callbacks = []
    monkeypatch.setattr(router.requests, "get", lambda url, callback: callbacks.append(callback))
    resolved = []
    router.resolved.connect(resolved.append)
    router.route("https://youtu.be/old", "auto")
    router.route("https://youtu.be/new", "")
    callbacks[0]([["video.example", {"api": True, "uri": "https://video.example"}]], None)
    assert resolved == ["https://youtu.be/new"]
    router.route("https://youtu.be/current", "auto")
    callbacks[1]([["bad", {"api": True, "uri": "http://bad"}],
                  ["video.example", {"api": True, "uri": "https://video.example"}]], None)
    assert resolved[-1] == "https://video.example/watch?v=current"
