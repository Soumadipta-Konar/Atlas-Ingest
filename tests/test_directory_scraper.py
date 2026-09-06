"""Unit tests for DirectoryScraper._find_next_page_url — deterministic, no network required."""
import pytest
from bs4 import BeautifulSoup
from src.crawlers.directory_scraper import DirectoryScraper


@pytest.fixture
def scraper():
    # DirectoryScraper requires no network for _find_next_page_url
    return DirectoryScraper.__new__(DirectoryScraper)


def make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


class TestFindNextPageUrlRelNext:
    def test_rel_next_link(self, scraper):
        html = '<html><body><a rel="next" href="/page/2">Next</a></body></html>'
        soup = make_soup(html)
        result = scraper._find_next_page_url(soup, "https://example.com/page/1")
        assert result == "https://example.com/page/2"

    def test_rel_next_absolute_href(self, scraper):
        html = '<html><body><a rel="next" href="https://other.com/page/2">Next</a></body></html>'
        soup = make_soup(html)
        result = scraper._find_next_page_url(soup, "https://example.com/page/1")
        assert result == "https://other.com/page/2"


class TestFindNextPageUrlTextButton:
    def test_next_text_button(self, scraper):
        html = '<html><body><a href="/p/3">Next page</a></body></html>'
        soup = make_soup(html)
        result = scraper._find_next_page_url(soup, "https://example.com/p/2")
        assert result == "https://example.com/p/3"

    def test_next_uppercase_button(self, scraper):
        html = '<html><body><a href="/p/4">NEXT</a></body></html>'
        soup = make_soup(html)
        result = scraper._find_next_page_url(soup, "https://example.com/p/3")
        assert result == "https://example.com/p/4"


class TestFindNextPageUrlNoNext:
    def test_no_next_returns_none(self, scraper):
        html = '<html><body><a href="/about">About</a></body></html>'
        soup = make_soup(html)
        result = scraper._find_next_page_url(soup, "https://example.com/page/1")
        assert result is None

    def test_empty_page_returns_none(self, scraper):
        html = '<html><body></body></html>'
        soup = make_soup(html)
        result = scraper._find_next_page_url(soup, "https://example.com/")
        assert result is None
