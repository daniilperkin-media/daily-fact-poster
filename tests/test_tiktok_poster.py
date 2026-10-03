"""Tests for the TikTok posting path: guards, draft flow, statuses, refresh."""
from unittest import mock

import pytest

from daily_fact_poster import tiktok_poster
from daily_fact_poster.constants import PLACEHOLDER_TIKTOK_ACCESS_TOKEN


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in (
        "TIKTOK_ACCESS_TOKEN",
        "TIKTOK_REFRESH_TOKEN",
        "TIKTOK_CLIENT_KEY",
        "TIKTOK_CLIENT_SECRET",
        "TIKTOK_PRIVACY_LEVEL",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def video(tmp_path):
    path = tmp_path / "video.mp4"
    path.write_bytes(b"fake-mp4-data")
    return str(path)


def _resp(status=200, payload=None, text=""):
    r = mock.Mock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    r.text = text
    return r


def _flow(monkeypatch, post_responses):
    """Patch requests inside tiktok_poster and return the recorded calls."""
    calls = []

    def fake_post(url, **kwargs):
        calls.append(("post", url, kwargs))
        return post_responses.pop(0)

    def fake_put(url, **kwargs):
        calls.append(("put", url, kwargs))
        return _resp(201, {})

    monkeypatch.setattr(tiktok_poster.requests, "post", fake_post)
    monkeypatch.setattr(tiktok_poster.requests, "put", fake_put)
    monkeypatch.setattr(tiktok_poster.time, "sleep", lambda s: None)
    return calls


def test_skips_without_token(video):
    with mock.patch.object(tiktok_poster.requests, "post") as p:
        assert tiktok_poster.post_video_to_tiktok(video) is False
    p.assert_not_called()


def test_placeholder_token_counts_as_missing(video):
    with mock.patch.object(tiktok_poster.requests, "post") as p:
        result = tiktok_poster.post_video_to_tiktok(
            video, access_token=PLACEHOLDER_TIKTOK_ACCESS_TOKEN
        )
    assert result is False
    p.assert_not_called()


def test_draft_flow_success(monkeypatch, video):
    calls = _flow(monkeypatch, [
        _resp(200, {"data": {"publish_id": "pid", "upload_url": "https://up"}}),
        _resp(200, {"data": {"status": "SEND_TO_USER_INBOX"}}),
    ])
    assert tiktok_poster.post_video_to_tiktok(video, access_token="tok") is True

    init_calls = [c for c in calls if c[0] == "post" and c[1] == tiktok_poster._INBOX_INIT_URL]
    assert len(init_calls) == 1
    payload = init_calls[0][2]["json"]
    assert "post_info" not in payload
    assert payload["source_info"]["source"] == "FILE_UPLOAD"


def test_publish_complete_is_success(monkeypatch, video):
    _flow(monkeypatch, [
        _resp(200, {"data": {"publish_id": "pid", "upload_url": "https://up"}}),
        _resp(200, {"data": {"status": "PUBLISH_COMPLETE"}}),
    ])
    assert tiktok_poster.post_video_to_tiktok(video, access_token="tok") is True


def test_failed_status_is_failure(monkeypatch, video):
    _flow(monkeypatch, [
        _resp(200, {"data": {"publish_id": "pid", "upload_url": "https://up"}}),
        _resp(200, {"data": {"status": "FAILED"}}),
    ])
    assert tiktok_poster.post_video_to_tiktok(video, access_token="tok") is False


def test_poll_timeout_is_failure(monkeypatch, video):
    monkeypatch.setattr(tiktok_poster, "_POLL_TIMEOUT", 0)
    _flow(monkeypatch, [
        _resp(200, {"data": {"publish_id": "pid", "upload_url": "https://up"}}),
    ])
    assert tiktok_poster.post_video_to_tiktok(video, access_token="tok") is False


def test_inbox_failure_falls_back_to_direct_post(monkeypatch, video):
    calls = _flow(monkeypatch, [
        _resp(403, {"error": {"code": "scope_not_authorized", "message": "nope"}}),
        _resp(200, {"data": {"privacy_level_options": ["SELF_ONLY"]}}),
        _resp(200, {"data": {"publish_id": "pid", "upload_url": "https://up"}}),
        _resp(200, {"data": {"status": "PUBLISH_COMPLETE"}}),
    ])
    monkeypatch.setenv("TIKTOK_PRIVACY_LEVEL", "PUBLIC_TO_EVERYONE")
    assert tiktok_poster.post_video_to_tiktok(video, access_token="tok") is True

    urls = [c[1] for c in calls if c[0] == "post"]
    assert urls[0] == tiktok_poster._INBOX_INIT_URL
    assert tiktok_poster._DIRECT_INIT_URL in urls
    direct_calls = [c for c in calls if c[0] == "post" and c[1] == tiktok_poster._DIRECT_INIT_URL]
    assert direct_calls[0][2]["json"]["post_info"]["privacy_level"] == "SELF_ONLY"


def test_expired_token_triggers_refresh(monkeypatch, video):
    monkeypatch.setattr(tiktok_poster, "refresh_access_token", lambda: "new-token")
    calls = _flow(monkeypatch, [
        _resp(401, {"error": {"code": "access_token_invalid", "message": "expired"}}),
        _resp(200, {"data": {"publish_id": "pid", "upload_url": "https://up"}}),
        _resp(200, {"data": {"status": "SEND_TO_USER_INBOX"}}),
    ])
    assert tiktok_poster.post_video_to_tiktok(video, access_token="old-token") is True

    init_calls = [c for c in calls if c[0] == "post" and c[1] == tiktok_poster._INBOX_INIT_URL]
    assert len(init_calls) == 2
    assert init_calls[1][2]["headers"]["Authorization"] == "Bearer new-token"
