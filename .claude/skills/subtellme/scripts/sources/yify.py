"""YIFY Subtitles scraper (movies, English-leaning).

Site: https://yifysubtitles.ch
Search:    /search?q=<title>
Movie page: /movie-imdb/tt<id>  (linked from search results)
Listing:   <table class="other-subtitle-table"> rows with rating, lang, link
Download:  /subtitle/<slug>.zip  (linked from each subtitle detail page)

These selectors change occasionally. If a request returns an empty match
list, inspect the page HTML and update the constants below.
"""

from __future__ import annotations

import logging
import urllib.parse
from pathlib import Path

from bs4 import BeautifulSoup

from .base import Match, Source, SourceError, extract_srts

log = logging.getLogger("subtellme.sources.yify")

BASE = "https://yifysubtitles.ch"
LANG_LABELS = {"en": "english", "es": "spanish"}


class YifySubtitles(Source):
    name = "yify"
    kinds = ("movie",)
    langs = ("en", "es")

    def search(self, title, lang, *, year=None, season=None):
        if season is not None:
            return []
        url = f"{BASE}/search?q={urllib.parse.quote(title)}"
        soup = BeautifulSoup(self._get(url).text, "html.parser")

        # Search result cards link to /movie-imdb/<imdb_id>.
        movie_links = [
            a.get("href")
            for a in soup.select("a")
            if a.get("href", "").startswith("/movie-imdb/")
        ]
        if not movie_links:
            return []

        # Take the top result; year is used only to disambiguate when present.
        movie_url = BASE + movie_links[0]
        if year:
            for href in movie_links:
                # YIFY pages embed the year in the title text near the link.
                if str(year) in href:
                    movie_url = BASE + href
                    break

        page = BeautifulSoup(self._get(movie_url).text, "html.parser")
        rows = page.select("table.other-subtitle-table tbody tr")
        wanted_lang = LANG_LABELS.get(lang, lang)

        matches: list[Match] = []
        for row in rows:
            lang_cell = row.select_one("span.sub-lang")
            link = row.select_one("a[href^='/subtitles/']")
            rating_cell = row.select_one("span.label")
            if not lang_cell or not link:
                continue
            if lang_cell.get_text(strip=True).lower() != wanted_lang:
                continue
            score = _safe_int(rating_cell.get_text(strip=True) if rating_cell else "0")
            detail_url = BASE + link["href"]
            matches.append(
                Match(
                    source=self.name,
                    title=title,
                    lang=lang,
                    url=detail_url,
                    year=year,
                    kind="movie",
                    score=float(score),
                )
            )
        return matches

    def download(self, match, dest_dir):
        # The detail page contains an "/subtitle/<slug>.zip" anchor.
        soup = BeautifulSoup(self._get(match.url).text, "html.parser")
        zip_link = None
        for a in soup.select("a[href]"):
            href = a["href"]
            if href.endswith(".zip") and "/subtitle/" in href:
                zip_link = href if href.startswith("http") else BASE + href
                break
        if not zip_link:
            raise SourceError("yify: zip link not found on detail page")
        payload = self._get(zip_link).content
        return extract_srts(payload, Path(dest_dir))


def _safe_int(text: str) -> int:
    try:
        return int(text.strip())
    except ValueError:
        return 0
