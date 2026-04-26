"""Subdivx scraper (Spanish movies and series).

Site: https://subdivx.com
Search: /inc/ajax.php?... (the public site moved to an AJAX-first design;
       the legacy form-encoded endpoint still works via POST):
        POST /inc/ajax.php
            action=getMoviesPaginate
            tabla=resultados
            buscar=<query>
        returns JSON with `aaData[*]` rows containing id, descripcion, etc.
Download: /descargar.php?id=<id>  -> .rar or .zip

Subdivx is the standard for Spanish; English is occasionally available but
we treat this source as `es` only.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from .base import Match, Source, SourceError, extract_srts, title_score

log = logging.getLogger("subtellme.sources.subdivx")

BASE = "https://subdivx.com"


class Subdivx(Source):
    name = "subdivx"
    kinds = ("movie", "series")
    langs = ("es",)
    rate_limit_s = 1.5

    def search(self, title, lang, *, year=None, season=None):
        if lang != "es":
            return []
        query = title
        if season is not None:
            query = f"{title} S{season:02d}"
        r = self._post(
            f"{BASE}/inc/ajax.php",
            data={
                "action": "getMoviesPaginate",
                "tabla": "resultados",
                "buscar": query,
            },
            headers={"X-Requested-With": "XMLHttpRequest", "Referer": BASE + "/"},
        )
        try:
            payload = r.json()
        except ValueError as e:
            raise SourceError("subdivx: response not JSON") from e

        rows = payload.get("aaData") or []
        matches: list[Match] = []
        for row in rows:
            sub_id = row.get("id")
            desc = _strip_tags(row.get("descripcion", "") or "")
            sub_title = row.get("titulo", "") or ""
            downloads = row.get("descargas") or 0
            if not sub_id:
                continue
            # Year filter (when supplied) on the description text.
            if year and str(year) not in (desc + sub_title):
                continue
            score = float(downloads) + title_score(query, sub_title) * 1000
            matches.append(
                Match(
                    source=self.name,
                    title=sub_title or title,
                    lang="es",
                    url=f"{BASE}/descargar.php?id={sub_id}",
                    year=year,
                    season=season,
                    kind="series" if season else "movie",
                    score=score,
                    extra={"description": desc},
                )
            )
        return matches

    def download(self, match, dest_dir):
        r = self._get(match.url, headers={"Referer": BASE + "/"})
        if not r.content:
            raise SourceError("subdivx: empty download")
        return extract_srts(r.content, Path(dest_dir))


def _strip_tags(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()
