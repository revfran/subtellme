"""Addic7ed scraper (TV series).

Site: https://www.addic7ed.com
Search:        /search.php?search=<query>&Submit=Search
Show page:     /show/<id>            -> table of seasons/episodes
Season page:   /ajax_loadShow.php?show=<id>&season=<n>&langs=&hd=0&hi=0
Subtitle row:  language column + "most updated" download link
Download:      /original/<file_id>/<version>  (Referer header required)

Addic7ed is hostile to scraping; obey the rate limit and the Referer rule.
If you see HTTP 403/redirects to the homepage, slow down further.
"""

from __future__ import annotations

import logging
import re
import urllib.parse
from pathlib import Path

from bs4 import BeautifulSoup

from .base import Match, Source, SourceError, extract_srts

log = logging.getLogger("subtellme.sources.addic7ed")

BASE = "https://www.addic7ed.com"
LANG_LABELS = {"en": "English", "es": ("Spanish", "Spanish (Latin America)")}


class Addic7ed(Source):
    name = "addic7ed"
    kinds = ("series",)
    langs = ("en", "es")
    rate_limit_s = 2.0

    def search(self, title, lang, *, year=None, season=None):
        if season is None:
            raise SourceError("addic7ed: season is required")

        # Step 1: search the show.
        q = urllib.parse.quote(title)
        soup = BeautifulSoup(
            self._get(f"{BASE}/search.php?search={q}&Submit=Search").text,
            "html.parser",
        )
        # Direct redirects to /show/<id> when there's a single match.
        show_id = _find_show_id(soup, BASE)
        if show_id is None:
            return []

        # Step 2: fetch the season's episode list via the ajax endpoint.
        season_url = (
            f"{BASE}/ajax_loadShow.php?show={show_id}&season={season}"
            "&langs=&hd=0&hi=0"
        )
        page = BeautifulSoup(
            self._get(season_url, headers={"Referer": f"{BASE}/show/{show_id}"}).text,
            "html.parser",
        )

        wanted = LANG_LABELS[lang] if isinstance(LANG_LABELS[lang], tuple) else (LANG_LABELS[lang],)
        rows_by_episode: dict[int, str] = {}
        for tr in page.select("tr.epeven"):
            cells = tr.find_all("td")
            if len(cells) < 10:
                continue
            try:
                ep_num = int(cells[1].get_text(strip=True))
            except ValueError:
                continue
            lang_cell = cells[3].get_text(strip=True)
            status = cells[5].get_text(strip=True).lower()
            if lang_cell not in wanted:
                continue
            if "completed" not in status:
                continue
            link = cells[9].find("a", href=True)
            if not link:
                continue
            href = link["href"]
            url = href if href.startswith("http") else BASE + href
            # Keep the first completed entry per episode (Addic7ed sorts by version).
            rows_by_episode.setdefault(ep_num, url)

        return [
            Match(
                source=self.name,
                title=title,
                lang=lang,
                url=url,
                season=season,
                kind="series",
                score=float(ep),
                extra={"episode": ep, "show_id": show_id},
            )
            for ep, url in sorted(rows_by_episode.items())
        ]

    def download(self, match, dest_dir):
        """For series we expect to be called once with the *list* of matches.

        The orchestrator handles series specially: it iterates `search()` and
        calls `download()` per episode. Here we download a single episode and
        save it as `<NN>.srt`.
        """
        ep = match.extra.get("episode")
        if ep is None:
            raise SourceError("addic7ed: missing episode number")
        referer = match.url.replace("/original/", "/serie/")
        r = self._get(match.url, headers={"Referer": BASE + "/"})
        if not r.content or r.headers.get("Content-Type", "").startswith("text/html"):
            raise SourceError("addic7ed: download blocked or empty")
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        out = dest / f"{int(ep):02d}.srt"
        out.write_bytes(r.content)
        return [out]


def _find_show_id(soup: BeautifulSoup, base: str) -> int | None:
    # Direct hit: /show/<id> linked from the results table.
    for a in soup.select("a[href^='/show/']"):
        m = re.match(r"^/show/(\d+)", a["href"])
        if m:
            return int(m.group(1))
    return None
