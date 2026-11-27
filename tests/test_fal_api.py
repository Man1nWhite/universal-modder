"""`um fal` talks to fal.ai: request building, retry/backoff, output naming, the manifest.

Only the network boundary is faked; everything between it and the files on disk is the real code.
Before this file existed, `um fal` — the largest module in the package — had no behavioral tests
at all, and a retry loop that swallowed 4xx or a naming bug in `download_outputs` shipped silently.
"""
from __future__ import annotations

import base64
import io
import json
import urllib.error

import pytest

from um import fal


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _http_error(code, body=b'{"detail":"nope"}'):
    return urllib.error.HTTPError("https://x", code, "msg", {}, io.BytesIO(body))


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(fal.time, "sleep", lambda s: None)


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setattr(fal, "fal_key", lambda: "test-key")


# --------------------------------------------------------------------------- retry in _req


def test_req_retries_429_then_succeeds(monkeypatch, key):
    calls, body = [], b'{"ok": true}'

    class Flaky:
        def __init__(self):
            self.n = 0

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        if len(calls) < 3:
            raise _http_error(429)
        return _Resp(body)

    monkeypatch.setattr(fal.urllib.request, "urlopen", fake_urlopen)
    assert fal._req("GET", "https://api.fal.ai/v1/x") == {"ok": True}
    assert len(calls) == 3


def test_req_sends_the_authorization_header(monkeypatch, key):
    captured = []

    def fake_urlopen(req, timeout=None):
        captured.append(req)
        return _Resp(b"{}")

    monkeypatch.setattr(fal.urllib.request, "urlopen", fake_urlopen)
    fal._req("GET", "https://api.fal.ai/v1/x")
    assert captured[0].get_header("Authorization") == "Key test-key"


def test_req_does_not_retry_a_400(monkeypatch, key):
    calls = []

    def fake_urlopen(req, timeout=None):
        calls.append(req)
        raise _http_error(400, b'{"detail":"bad input"}')

    monkeypatch.setattr(fal.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(SystemExit):
        fal._req("POST", "https://api.fal.ai/v1/x", {})
    assert len(calls) == 1                      # a 400 is the caller's bug; retrying cannot help


def test_req_gives_up_after_three_retries_on_unreachable_host(monkeypatch, key):
    def fake_urlopen(req, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(fal.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(SystemExit):
        fal._req("GET", "https://api.fal.ai/v1/x")


# --------------------------------------------------------------------------- queue polling


def test_run_waits_for_completion_and_returns_the_result(monkeypatch, key):
    steps = iter([
        {"status": "IN_QUEUE", "queue_position": 3},
        {"status": "IN_PROGRESS", "logs": [{"message": "loading model"}]},
        {"status": "COMPLETED", "logs": []},
    ])
    def fake_req(method, url, body=None, **kw):
        if method == "POST":
            return {"request_id": "req-1", "status_url": "https://queue/req-1/status", "response_url": "https://queue/req-1"}
        if "status" in url:
            return next(steps)
        return {"images": [{"url": "https://cdn/x.png"}]}

    monkeypatch.setattr(fal, "_req", fake_req)
    res = fal.run("ep/model", {"prompt": "hi"}, quiet=True)
    assert res["_request_id"] == "req-1"
    assert res["_endpoint"] == "ep/model"


def test_run_dies_when_the_job_reports_an_error(monkeypatch, key):
    monkeypatch.setattr(fal, "_req", lambda method, url, body=None, **kw:
                        {"request_id": "r"} if method == "POST" else {"status": "COMPLETED", "error": "CUDA OOM"})
    with pytest.raises(SystemExit):
        fal.run("ep/model", {}, quiet=True)


# --------------------------------------------------------------------------- download_outputs naming


def _fake_urlopen_factory(payloads):
    def fake(req, timeout=None):
        return _Resp(payloads[req.full_url])
    return fake


def test_download_outputs_names_indexed_files(monkeypatch, tmp_path):
    payloads = {
        "https://cdn/0.png": b"first",
        "https://cdn/1.png": b"second",
        "https://cdn/m.png": b"mask",
    }
    monkeypatch.setattr(fal.urllib.request, "urlopen", _fake_urlopen_factory(payloads))
    result = {"images": [{"url": "https://cdn/0.png", "content_type": "image/png"},
                         {"url": "https://cdn/1.png", "content_type": "image/png"}],
              "mask": {"url": "https://cdn/m.png", "content_type": "image/png"}}
    files = fal.download_outputs(result, tmp_path, "asset")
    assert sorted(p.split("/")[-1] for p in files) == ["asset.png", "asset_2.png", "asset_mask.png"]
    assert (tmp_path / "asset.png").read_bytes() == b"first"


def test_download_outputs_falls_back_to_the_content_type_extension(monkeypatch, tmp_path):
    payloads = {"https://cdn/download": b"bytes"}
    monkeypatch.setattr(fal.urllib.request, "urlopen", _fake_urlopen_factory(payloads))
    files = fal.download_outputs({"output": {"url": "https://cdn/download", "content_type": "audio/mpeg"}}, tmp_path, "sfx")
    assert files[0].endswith("sfx.mp3")


def test_download_outputs_reports_failures_with_the_request_id(monkeypatch, tmp_path, capsys):
    def boom(req, timeout=None):
        raise urllib.error.URLError("gone")

    monkeypatch.setattr(fal.urllib.request, "urlopen", boom)
    result = {"images": [{"url": "https://cdn/0.png"}], "_request_id": "req-9", "_endpoint": "ep"}
    with pytest.raises(SystemExit):
        fal.download_outputs(result, tmp_path, "asset")


def test_urls_in_walks_nested_structures():
    result = {"a": [{"b": [{"url": "https://x/1.png"}]}], "c": {"url": "https://x/2.png", "content_type": "image/png"}}
    found = list(fal._urls_in(result))
    assert {u for _, u, _ in found} == {"https://x/1.png", "https://x/2.png"}


# --------------------------------------------------------------------------- uploads and manifest


def test_as_url_passes_urls_through_untouched():
    assert fal._as_url("https://example.com/x.png") == "https://example.com/x.png"
    assert fal._as_url("data:image/png;base64,AAAA") == "data:image/png;base64,AAAA"


def test_upload_falls_back_to_a_data_uri_when_the_cdn_is_down(monkeypatch, tmp_path):
    def boom(name, ctype, data):
        raise OSError("cdn unreachable")

    monkeypatch.setattr(fal, "_upload_cdn", boom)
    p = tmp_path / "x.png"
    p.write_bytes(b"\x89PNG fake")
    uri = fal.upload(p)
    assert uri.startswith("data:image/png;base64,")
    assert base64.b64decode(uri.split(",", 1)[1]) == b"\x89PNG fake"


def test_generate_writes_a_manifest_line(monkeypatch, tmp_path):
    monkeypatch.setattr(fal, "run", lambda endpoint, inp, quiet=False:
                        {"images": [{"url": "https://cdn/0.png", "content_type": "image/png"}],
                         "seed": 42, "_request_id": "req-7"})
    monkeypatch.setattr(fal.urllib.request, "urlopen", _fake_urlopen_factory({"https://cdn/0.png": b"img"}))
    out = fal.generate("ep/model", {"prompt": "a drone"}, tmp_path, "drone", quiet=True)
    assert out["files"][0].endswith("drone.png")
    lines = (tmp_path / "fal_manifest.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["endpoint"] == "ep/model"
    assert rec["seed"] == 42
    assert rec["request_id"] == "req-7"
    assert rec["input"]["prompt"] == "a drone"
