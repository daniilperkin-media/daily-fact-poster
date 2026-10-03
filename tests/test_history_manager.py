"""Pytest tests for pure functions in Daily_Fact_Poster/history_manager.py.

Targets:
    - is_duplicate
    - get_past_topics
    - record_post
    - load_history / save_history (against a temp file)
"""
import pytest

from daily_fact_poster import history_manager


@pytest.fixture
def isolated_history(monkeypatch, tmp_path):
    """Redirect history_manager's HISTORY_FILE to a temp path and return a fresh history dict."""
    fake_file = tmp_path / "history.json"
    monkeypatch.setattr(history_manager, "HISTORY_FILE", str(fake_file))
    return history_manager.load_history()


# ---------------------------------------------------------------------------
# get_past_topics
# ---------------------------------------------------------------------------

class TestGetPastTopics:
    def test_returns_list(self, isolated_history):
        topics = history_manager.get_past_topics(isolated_history)
        assert topics == []

    def test_returns_existing_topics(self, isolated_history):
        isolated_history["past_topics"] = ["Cats", "Dogs"]
        assert history_manager.get_past_topics(isolated_history) == ["Cats", "Dogs"]

    def test_missing_key_returns_empty(self, isolated_history):
        del isolated_history["past_topics"]
        assert history_manager.get_past_topics(isolated_history) == []


# ---------------------------------------------------------------------------
# is_duplicate
# ---------------------------------------------------------------------------

class TestIsDuplicate:
    def test_empty_history_not_duplicate(self, isolated_history):
        assert history_manager.is_duplicate(isolated_history, "New Title", "short fact") is False

    def test_no_keyword_overlap_not_duplicate(self, isolated_history):
        isolated_history["past_topics"] = ["Elephants sleeping"]
        # "abc" and "def" are short words (len<=4) -> no keywords extracted
        assert history_manager.is_duplicate(isolated_history, "abc def", "ghi jkl") is False

    def test_duplicate_detected(self, isolated_history):
        """Two shared long words => duplicate."""
        isolated_history["past_topics"] = ["Interesting facts about dolphins"]
        # "dolphins" and "facts" are both shared long words (len > 4).
        result = history_manager.is_duplicate(
            isolated_history,
            "Amazing dolphins",
            "dolphins facts review",
        )
        assert result is True

    def test_single_shared_word_not_duplicate(self, isolated_history):
        """Need >= 2 shared keywords to count as duplicate."""
        isolated_history["past_topics"] = ["Interesting elephants"]
        # Only "elephants" is shared (and "interesting" is also shared actually)
        # "interesting" len 11 > 4, "elephants" len 9 > 4 -> 2 shared => duplicate.
        # Use a topic where only one long word overlaps.
        isolated_history["past_topics"] = ["elephants sleeping quietly"]
        result = history_manager.is_duplicate(
            isolated_history,
            "elephants running",
            "quick brown fox",
        )
        # "elephants" shared, "running"/"quick"/"brown" not in past -> only 1 overlap
        assert result is False

    def test_checks_only_recent_200(self, isolated_history):
        """is_duplicate only inspects the last 200 past_topics."""
        # Put a duplicate-worthy topic at position 0, then fill 200+ decoys after it.
        isolated_history["past_topics"] = ["Interesting facts about dolphins"]
        isolated_history["past_topics"].extend(["decoy topic number"] * 250)
        # The real duplicate topic is now outside the last-200 window.
        result = history_manager.is_duplicate(
            isolated_history,
            "Amazing dolphins",
            "Dolphins are mammals",
        )
        assert result is False

    def test_keywords_ignore_short_words(self, isolated_history):
        """Words of length <= 4 are ignored when building keywords."""
        isolated_history["past_topics"] = ["cats and dogs sleeping"]
        # "cats"(4), "and"(3), "dogs"(4) all <=4 ignored; "sleeping"(8) is keyword.
        # New text: "sleeping" + "running"(7). Only "sleeping" shared => not duplicate.
        result = history_manager.is_duplicate(
            isolated_history,
            "sleeping running",
            "quickly jumping",
        )
        assert result is False


# ---------------------------------------------------------------------------
# record_post
# ---------------------------------------------------------------------------

class TestRecordPost:
    def test_appends_topic(self, isolated_history):
        fact_data = {"title": "My Fact", "fact_short": "short", "category": "science"}
        history_manager.record_post(isolated_history, fact_data, "http://img/1.png", ["TikTok"])
        assert isolated_history["past_topics"] == ["My Fact"]

    def test_appends_post_history_entry(self, isolated_history):
        fact_data = {"title": "My Fact", "fact_short": "short", "category": "science"}
        history_manager.record_post(isolated_history, fact_data, "http://img/1.png", ["TikTok"])
        entry = isolated_history["posts_history"][0]
        assert entry["title"] == "My Fact"
        assert entry["image_url"] == "http://img/1.png"
        assert entry["platforms"] == ["TikTok"]
        assert entry["category"] == "science"

    def test_updates_stats(self, isolated_history):
        fact_data = {"title": "My Fact", "fact_short": "short", "category": "science"}
        history_manager.record_post(isolated_history, fact_data, "url1", ["TikTok", "Telegram"])
        stats = isolated_history["stats"]
        assert stats["total_posts"] == 1
        assert stats["last_run"] is not None
        assert stats["platform_counts"]["TikTok"] == 1
        assert stats["platform_counts"]["Telegram"] == 1

    def test_multiple_posts_increment_counts(self, isolated_history):
        for i in range(3):
            history_manager.record_post(
                isolated_history,
                {"title": f"Fact {i}", "fact_short": "x", "category": "c"},
                f"url{i}",
                ["TikTok"],
            )
        assert isolated_history["stats"]["total_posts"] == 3
        assert isolated_history["stats"]["platform_counts"]["TikTok"] == 3
        assert len(isolated_history["past_topics"]) == 3


# ---------------------------------------------------------------------------
# load_history / save_history round-trip
# ---------------------------------------------------------------------------

class TestLoadSaveHistory:
    def test_fresh_structure_when_no_file(self, monkeypatch, tmp_path):
        fake_file = tmp_path / "missing.json"
        monkeypatch.setattr(history_manager, "HISTORY_FILE", str(fake_file))
        data = history_manager.load_history()
        assert data["past_topics"] == []
        assert data["posts_history"] == []
        assert data["stats"]["total_posts"] == 0

    def test_round_trip(self, monkeypatch, tmp_path):
        fake_file = tmp_path / "history.json"
        monkeypatch.setattr(history_manager, "HISTORY_FILE", str(fake_file))
        data = history_manager.load_history()
        history_manager.record_post(
            data,
            {"title": "Round Trip", "fact_short": "short", "category": "test"},
            "url",
            ["TikTok"],
        )
        history_manager.save_history(data)

        reloaded = history_manager.load_history()
        assert reloaded["past_topics"] == ["Round Trip"]
        assert reloaded["stats"]["total_posts"] == 1

    def test_save_trims_past_topics(self, monkeypatch, tmp_path):
        fake_file = tmp_path / "history.json"
        monkeypatch.setattr(history_manager, "HISTORY_FILE", str(fake_file))
        data = history_manager.load_history()
        # Exceed MAX_TOPICS
        data["past_topics"] = [f"topic {i}" for i in range(history_manager.MAX_TOPICS + 50)]
        history_manager.save_history(data)

        reloaded = history_manager.load_history()
        assert len(reloaded["past_topics"]) == history_manager.MAX_TOPICS
        # Most recent topics retained
        assert reloaded["past_topics"][-1] == f"topic {history_manager.MAX_TOPICS + 49}"

    def test_load_backfills_stats(self, monkeypatch, tmp_path):
        """Old history files without a 'stats' key get one back-filled."""
        import json

        fake_file = tmp_path / "old_history.json"
        fake_file.write_text(json.dumps({"past_topics": ["x"], "posts_history": []}), encoding="utf-8")
        monkeypatch.setattr(history_manager, "HISTORY_FILE", str(fake_file))

        data = history_manager.load_history()
        assert "stats" in data
        assert data["stats"]["total_posts"] == 0

    def test_corrupt_json_is_quarantined_and_fresh(self, monkeypatch, tmp_path):
        """A truncated/corrupt history.json is moved aside (not crashed on), and
        load_history returns a fresh structure so the run can proceed."""
        fake_file = tmp_path / "history.json"
        fake_file.write_text("{ not valid json !!!", encoding="utf-8")
        monkeypatch.setattr(history_manager, "HISTORY_FILE", str(fake_file))

        data = history_manager.load_history()
        assert data["past_topics"] == []
        assert data["stats"]["total_posts"] == 0
        # The corrupt original was renamed aside, not overwritten.
        quarantined = [p for p in fake_file.parent.iterdir() if "corrupt" in p.name]
        assert len(quarantined) == 1
        assert not fake_file.exists()

    def test_non_object_root_is_quarantined(self, monkeypatch, tmp_path):
        """A valid-JSON-but-wrong-shape file (root is a list, not object) is
        also treated as corrupt and quarantined."""
        import json

        fake_file = tmp_path / "history.json"
        fake_file.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        monkeypatch.setattr(history_manager, "HISTORY_FILE", str(fake_file))

        data = history_manager.load_history()
        assert data["posts_history"] == []
        quarantined = [p for p in tmp_path.iterdir() if "corrupt" in p.name]
        assert len(quarantined) == 1
