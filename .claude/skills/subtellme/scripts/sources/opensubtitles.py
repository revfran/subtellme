"""OpenSubtitles.com API source (movies + series, multilingual).

API docs: https://opensubtitles.stoplight.io/docs/opensubtitles-api
Search:   GET  /api/v1/subtitles?query=<q>&languages=<lang>&season_number=<n>...
Download: POST /api/v1/download  {"file_id": <id>}  → {"link": "<url>"}
Login:    POST /api/v1/login     {"username": ..., "password": ...} → token

Requires env vars:
    OPENSUBTITLES_API_KEY   (required)
    OPENSUBTITLES_USERNAME  (required for download)
    OPENSUBTITLES_PASSWORD  (required for download)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from .base import Match, Source, SourceError

log = logging.getLogger("subtellme.sources.opensubtitles")

API_BASE = "https://api.opensubtitles.com/api/v1"
USER_AGENT = "subtellme v1.0"


class OpenSubtitles(Source):
    name = "opensubtitles"
    kinds = ("movie", "series")
    langs = ("en", "es")
    rate_limit_s = 1.0

    def __init__(self) -> None:
        super().__init__()
        self._api_key = os.environ.get("OPENSUBTITLES_API_KEY", "")
        self._username = os.environ.get("OPENSUBTITLES_USERNAME", "")
        self._password = os.environ.get("OPENSUBTITLES_PASSWORD", "")
        self._token: str | None = None
        self._remaining: int | None = None
        self._reset_time: str | None = None
        if not self._api_key:
            raise SourceError(
                "opensubtitles: OPENSUBTITLES_API_KEY env var not set"
            )
        # Override default headers with API-specific ones.
        self._client.headers.update({
            "Api-Key": self._api_key,
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def _login(self) -> None:
        """Authenticate and store the session token."""
        if self._token:
            return
        if not self._username or not self._password:
            raise SourceError(
                "opensubtitles: OPENSUBTITLES_USERNAME and "
                "OPENSUBTITLES_PASSWORD env vars required for download"
            )
        self._wait()
        r = self._client.post(
            f"{API_BASE}/login",
            json={"username": self._username, "password": self._password},
        )
        if r.status_code != 200:
            raise SourceError(f"opensubtitles: login failed ({r.status_code})")
        data = r.json()
        self._token = data.get("token")
        if not self._token:
            raise SourceError("opensubtitles: login returned no token")
        self._client.headers["Authorization"] = self._token
        log.info("logged in as %s", self._username)

    def search(self, title, lang, *, year=None, season=None):
        params: dict[str, str] = {
            "query": title,
            "languages": lang,
        }
        if season is not None:
            params["type"] = "episode"
            params["season_number"] = str(season)
        else:
            params["type"] = "movie"
        if year:
            params["year"] = str(year)

        # Exclude AI/machine translations for quality.
        params["ai_translated"] = "exclude"
        params["machine_translated"] = "exclude"

        r = self._get(f"{API_BASE}/subtitles", params=params)
        try:
            payload = r.json()
        except ValueError as e:
            raise SourceError("opensubtitles: response not JSON") from e

        results = payload.get("data") or []
        matches: list[Match] = []
        for item in results:
            attrs = item.get("attributes", {})
            files = attrs.get("files") or []
            if not files:
                continue
            file_id = files[0].get("file_id")
            if not file_id:
                continue

            details = attrs.get("feature_details") or {}
            ep = details.get("episode_number") or attrs.get("episode_number") or 0
            kind = "series" if season is not None else "movie"
            matches.append(
                Match(
                    source=self.name,
                    title=attrs.get("release") or title,
                    lang=lang,
                    url=f"{API_BASE}/download",
                    year=details.get("year") or year,
                    season=season,
                    kind=kind,
                    score=float(attrs.get("download_count", 0)),
                    extra={
                        "file_id": file_id,
                        "episode": ep,
                        "feature_type": details.get("feature_type", ""),
                    },
                )
            )
        return matches

    def download(self, match, dest_dir):
        self._login()
        file_id = match.extra.get("file_id")
        if not file_id:
            raise SourceError("opensubtitles: missing file_id")

        # Check remaining quota before burning a download.
        if self._remaining is not None and self._remaining <= 0:
            raise SourceError(
                "opensubtitles: daily download quota exhausted "
                f"(resets at {self._reset_time or 'unknown'})"
            )

        # POST to get the download link.
        self._wait()
        r = self._client.post(
            f"{API_BASE}/download",
            json={"file_id": file_id},
        )
        if r.status_code == 406:
            raise SourceError("opensubtitles: daily download quota exhausted")
        if r.status_code != 200:
            raise SourceError(
                f"opensubtitles: download request failed ({r.status_code}): "
                f"{r.text[:200]}"
            )
        data = r.json()
        self._remaining = data.get("remaining")
        self._reset_time = data.get("reset_time_utc")
        if self._remaining is not None:
            log.info("downloads remaining today: %d", self._remaining)
        link = data.get("link")
        if not link:
            raise SourceError("opensubtitles: no download link in response")

        # GET the actual subtitle file.
        self._wait()
        content = self._client.get(link).content
        if not content:
            raise SourceError("opensubtitles: empty subtitle file")

        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        ep = match.extra.get("episode", 0)
        if match.kind == "series" and ep:
            out = dest / f"{int(ep):02d}.srt"
        else:
            out = dest / "movie.srt"
        out.write_bytes(content)
        return [out]
