"""Tests for http_utils retry policy and script_generator validation."""
from unittest import mock

import pytest
import requests

from daily_fact_poster import http_utils, script_generator


def _http_error(status):
    resp = requests.Response()
    resp.status_code = status
    return requests.HTTPError(response=resp)


def _resp(status):
    r = mock.Mock()
    if status >= 400:
        r.raise_for_status.side_effect = _http_error(status)
    return r


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(http_utils.time, "sleep", lambda s: None)


def test_client_error_fails_fast():
    with mock.patch.object(http_utils.requests, "get", return_value=_resp(401)) as g:
        with pytest.raises(requests.HTTPError):
            http_utils.get_with_retry("http://x", retries=3)
    assert g.call_count == 1


@pytest.mark.parametrize("status", [429, 503])
def test_transient_errors_are_retried(status):
    ok = _resp(200)
    with mock.patch.object(http_utils.requests, "post", side_effect=[_resp(status), ok]) as p:
        assert http_utils.post_with_retry("http://x", retries=3) is ok
    assert p.call_count == 2


def test_connection_error_retried_then_raised():
    with mock.patch.object(http_utils.requests, "get", side_effect=requests.ConnectionError()) as g:
        with pytest.raises(requests.ConnectionError):
            http_utils.get_with_retry("http://x", retries=3)
    assert g.call_count == 3


GOOD = '{"title": "T", "fact_short": "f", "virality_score": "9", "slides": [{"text": "a"}]}'
NO_SLIDES = '{"title": "T", "fact_short": "f", "virality_score": 9, "slides": []}'


@pytest.fixture
def _env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-real-looking-key")
    monkeypatch.setattr(script_generator, "is_duplicate", lambda *a: False)
    monkeypatch.setattr(script_generator, "fallback_gemini_fact", lambda *a, **k: {"fallback": True})


def test_string_score_accepted(_env, monkeypatch):
    monkeypatch.setattr(script_generator, "call_openrouter_llm", lambda *a: GOOD)
    assert script_generator.generate_multi_scene_script([], history={})["title"] == "T"


def test_invalid_slides_regenerated(_env, monkeypatch):
    replies = iter([NO_SLIDES, "```json\n" + GOOD + "\n```"])
    monkeypatch.setattr(script_generator, "call_openrouter_llm", lambda *a: next(replies))
    assert script_generator.generate_multi_scene_script([], history={})["title"] == "T"


def test_all_invalid_falls_back(_env, monkeypatch):
    monkeypatch.setattr(script_generator, "call_openrouter_llm", lambda *a: NO_SLIDES)
    result = script_generator.generate_multi_scene_script([], history={})
    assert result["fallback"] is True
    # Fallback facts gain a synthesised slide list so the pipeline can still render.
    assert result["slides"][0]["text"] == "Did You Know?"
