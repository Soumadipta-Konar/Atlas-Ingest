"""Unit tests for DateNormalizer — deterministic, no network required."""
import pytest
from datetime import datetime, timedelta, timezone
from src.crawlers.news_jobs_scraper import DateNormalizer

IST = timezone(timedelta(hours=5, minutes=30))


@pytest.fixture
def normalizer():
    return DateNormalizer()


class TestDateNormalizerNone:
    def test_none_returns_near_now(self, normalizer):
        before = datetime.now(IST)
        result = normalizer.normalize(None)
        after = datetime.now(IST)
        assert before <= result <= after

    def test_empty_string_returns_near_now(self, normalizer):
        before = datetime.now(IST)
        result = normalizer.normalize("")
        after = datetime.now(IST)
        assert before <= result <= after


class TestDateNormalizerRelative:
    def test_hours_ago(self, normalizer):
        result = normalizer.normalize("3 hours ago")
        expected = datetime.now(IST) - timedelta(hours=3)
        # Allow 2-second tolerance
        assert abs((result - expected).total_seconds()) < 2

    def test_days_ago(self, normalizer):
        result = normalizer.normalize("2 days ago")
        expected = datetime.now(IST) - timedelta(days=2)
        assert abs((result - expected).total_seconds()) < 2

    def test_singular_hour(self, normalizer):
        result = normalizer.normalize("1 hour ago")
        expected = datetime.now(IST) - timedelta(hours=1)
        assert abs((result - expected).total_seconds()) < 2


class TestDateNormalizerRFC2822:
    def test_rfc2822_with_timezone(self, normalizer):
        # Standard RSS date format
        result = normalizer.normalize("Mon, 01 Jan 2024 12:00:00 +0000")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1

    def test_iso8601_utc(self, normalizer):
        result = normalizer.normalize("2024-06-15T08:30:00Z")
        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15


class TestDateNormalizerMalformed:
    def test_garbage_string_returns_near_now(self, normalizer):
        before = datetime.now(IST)
        result = normalizer.normalize("not-a-date-at-all!!!")
        after = datetime.now(IST)
        assert before <= result <= after
