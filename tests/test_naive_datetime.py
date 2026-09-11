"""Unit tests for naive datetime handling — verifies Fix #4."""
import pytest
from datetime import datetime, timedelta, timezone
from src.crawlers.news_jobs_scraper import DateNormalizer, NewsJobsScraper

IST = timezone(timedelta(hours=5, minutes=30))


@pytest.fixture
def normalizer():
    return DateNormalizer()


class TestNaiveDatetimeFix:
    """Fix #4: parsedate_to_datetime can return naive datetimes when the feed
    omits a timezone offset. These must be converted to aware datetimes to
    prevent TypeError in is_fresh()."""

    def test_rfc2822_without_timezone_returns_aware(self, normalizer):
        """Date string with no timezone offset should still return aware datetime."""
        result = normalizer.normalize("Mon, 01 Jan 2024 12:00:00")
        assert result.tzinfo is not None, "Expected an aware datetime, got naive"

    def test_rfc2822_without_timezone_assumes_utc_then_converts_to_ist(self, normalizer):
        """A tz-less RFC2822 date should be treated as UTC, then converted to IST."""
        result = normalizer.normalize("Mon, 01 Jan 2024 12:00:00")
        # UTC 12:00 → IST 17:30
        assert result.hour == 17
        assert result.minute == 30

    def test_is_fresh_does_not_crash_on_naive_input(self, normalizer):
        """is_fresh() should not raise TypeError on the result of normalize()."""
        scraper = NewsJobsScraper.__new__(NewsJobsScraper)
        scraper.normalizer = normalizer
        
        # This was the exact crash scenario from bug #4
        dt = normalizer.normalize("Mon, 01 Jan 2024 12:00:00")
        # Should not raise TypeError: can't subtract offset-naive and offset-aware datetimes
        result = scraper.is_fresh(dt)
        assert isinstance(result, bool)

    def test_rfc2822_with_timezone_still_works(self, normalizer):
        """Dates WITH timezone should continue working as before."""
        result = normalizer.normalize("Mon, 01 Jan 2024 12:00:00 +0000")
        assert result.tzinfo is not None
        assert result.year == 2024

    def test_all_normalized_dates_are_aware(self, normalizer):
        """Every possible path through normalize() should return aware datetimes."""
        test_cases = [
            None,                                    # None → now
            "",                                      # empty → now
            "3 hours ago",                           # relative hours
            "2 days ago",                            # relative days
            "Mon, 01 Jan 2024 12:00:00 +0000",     # RFC2822 with tz
            "Mon, 01 Jan 2024 12:00:00",            # RFC2822 without tz (bug #4)
            "2024-06-15T08:30:00Z",                 # ISO8601 UTC
            "not-a-date-at-all!!!",                  # garbage → now
        ]
        for date_str in test_cases:
            result = normalizer.normalize(date_str)
            assert result.tzinfo is not None, f"normalize({date_str!r}) returned naive datetime"
