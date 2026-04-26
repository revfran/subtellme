"""Podnapisi scraper (multilingual fallback).

Site: https://www.podnapisi.net
Search (JSON): /subtitles/search/advanced.json?keywords=<q>&language=<iso>&seasons=<n>
              language uses 3-letter codes ("eng", "spa")
Download:      /subtitles/<id>/download   -> zip or .srt

Podnapisi exposes a stable JSON endpoint, so this is the most resilient
source. We use it as the chain's last resort regardless of language.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .base import Match, Source, SourceError, extract_srts

log = logging.getLogger("subtellme.sources.podnapisi")

BASE = "https://www.podnapisi.net"
LANG_ISO3 = {"en": "en", "es": "es"}  # endpoint accepts 2-letter too


class Podnapisi(Source):
    name = "podnapisi"
    kinds = ("movie", "series")
    langs = ("en", "es")

    def search(self, title, lang, *, year=None, season=None):
        params = {
            "keywords": title,
            "language": LANG_ISO3.get(lang, lang),
        }
        if year:
            params["year"] = str(year)
        if season is not None:
            params["seasons"] = str(season)
            params["movie_type"] = "tv-series"
        else:
            params["movie_type"] = "movie"

        r = self._get(
            f"{BASE}/subtitles/search/advanced.json",
            params=params,
            headers={"Accept": "application/json"},
        )
        try:
            payload = r.json()
        except ValueError as e:
            raise SourceError("podnapisi: response not JSON") from e

        results = payload.get("data") or []
        matches: list[Match] = []
        for item in results:
            sid = item.get("id")
            if not sid:
                continue
            ep = item.get("episode") or 0
            downloads = item.get("stats", {}).get("downloads", 0)
            url = f"{BASE}/subtitles/{sid}/download"
            matches.append(
                Match(
                    source=self.name,
                    title=item.get("title") or title,
                    lang=lang,
                    url=url,
                    year=item.get("year") or year,
                    season=season,
                    kind="series" if season is not None else "movie",
                    score=float(downloads),
                    extra={"episode": ep, "id": sid},
                )
            )
        return matches

    def download(self, match, dest_dir):
        r = self._get(match.url, headers={"Referer": BASE + "/"})
        if not r.content:
            raise SourceError("podnapisi: empty download")
        files = extract_srts(r.content, Path(dest_dir))
        ep = match.extra.get("episode") or 0
        if match.kind == "series" and ep and len(files) == 1:
            target = Path(dest_dir) / f"{int(ep):02d}.srt"
            files[0].rename(target)
            return [target]
        return files
