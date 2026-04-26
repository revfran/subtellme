"""Base interface and shared HTTP/archive utilities for subtitle sources.

Every source implements `Source`. The orchestrator picks sources by content
type (movie vs series) and language, calls `search()`, then `download()` on
the best match. Implementations are intentionally minimal: when a site
changes its HTML, only the affected file under this package needs editing.
"""

from __future__ import annotations

import io
import logging
import shutil
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import httpx

log = logging.getLogger("subtellme.sources")

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class SourceError(RuntimeError):
    """Raised when a source cannot fulfil a request (no match, network, etc.)."""


@dataclass
class Match:
    """A subtitle candidate returned by `Source.search`."""

    source: str
    title: str
    lang: str
    url: str
    year: int | None = None
    season: int | None = None
    kind: str = "movie"  # "movie" or "series"
    score: float = 0.0  # higher is better; downloads/rating-derived
    extra: dict = field(default_factory=dict)


class Source:
    """Abstract base. Subclasses set `name` and the supported `kinds`/`langs`."""

    name: str = "base"
    kinds: tuple[str, ...] = ("movie", "series")
    langs: tuple[str, ...] = ("en",)
    rate_limit_s: float = 1.0  # min seconds between requests to this host
    timeout_s: float = 20.0

    def __init__(self) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en,es;q=0.8"},
            follow_redirects=True,
            timeout=self.timeout_s,
        )
        self._last_request = 0.0

    # ---- public API -------------------------------------------------------

    def supports(self, kind: str, lang: str) -> bool:
        return kind in self.kinds and lang in self.langs

    def search(
        self,
        title: str,
        lang: str,
        *,
        year: int | None = None,
        season: int | None = None,
    ) -> list[Match]:
        raise NotImplementedError

    def download(self, match: Match, dest_dir: Path) -> list[Path]:
        """Download subtitle(s) for `match` into `dest_dir`. Return .srt paths."""
        raise NotImplementedError

    # ---- helpers shared by subclasses ------------------------------------

    def _get(self, url: str, **kw) -> httpx.Response:
        self._wait()
        log.debug("GET %s", url)
        for attempt in range(3):
            try:
                r = self._client.get(url, **kw)
                r.raise_for_status()
                return r
            except (httpx.HTTPError,) as e:
                if attempt == 2:
                    raise SourceError(f"GET {url} failed: {e}") from e
                time.sleep(2 ** attempt)
        raise SourceError("unreachable")

    def _post(self, url: str, **kw) -> httpx.Response:
        self._wait()
        log.debug("POST %s", url)
        for attempt in range(3):
            try:
                r = self._client.post(url, **kw)
                r.raise_for_status()
                return r
            except httpx.HTTPError as e:
                if attempt == 2:
                    raise SourceError(f"POST {url} failed: {e}") from e
                time.sleep(2 ** attempt)
        raise SourceError("unreachable")

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.rate_limit_s:
            time.sleep(self.rate_limit_s - elapsed)
        self._last_request = time.monotonic()


# ---------- archive extraction ------------------------------------------------

def extract_srts(archive_bytes: bytes, dest_dir: Path) -> list[Path]:
    """Save .srt files from a zip or rar payload (or a single .srt) into `dest_dir`.

    Returns the paths of the extracted .srt files, sorted.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    head = archive_bytes[:4]

    if head[:2] == b"PK":  # zip
        return _extract_zip(archive_bytes, dest_dir)
    if head[:4] in (b"Rar!", b"\x52\x61\x72\x21"):
        return _extract_rar(archive_bytes, dest_dir)
    # treat as a raw .srt
    out = dest_dir / "subtitle.srt"
    out.write_bytes(archive_bytes)
    return [out]


def _extract_zip(payload: bytes, dest_dir: Path) -> list[Path]:
    out: list[Path] = []
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".srt"):
                continue
            target = dest_dir / Path(name).name
            with zf.open(name) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            out.append(target)
    return sorted(out)


def _extract_rar(payload: bytes, dest_dir: Path) -> list[Path]:
    try:
        import rarfile  # type: ignore[import-untyped]
    except ImportError as e:
        raise SourceError("rarfile not installed; pip install rarfile") from e
    if shutil.which("unrar") is None:
        raise SourceError(
            "unrar binary not found on PATH (install `unrar` or `unar`)"
        )
    tmp = dest_dir / "_archive.rar"
    tmp.write_bytes(payload)
    out: list[Path] = []
    try:
        with rarfile.RarFile(tmp) as rf:
            for name in rf.namelist():
                if not name.lower().endswith(".srt"):
                    continue
                target = dest_dir / Path(name).name
                with rf.open(name) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                out.append(target)
    finally:
        tmp.unlink(missing_ok=True)
    return sorted(out)


# ---------- common scoring ----------------------------------------------------

def title_score(query: str, candidate: str) -> float:
    """Cheap similarity for ranking: shared lowercased word ratio."""
    q = {w for w in query.lower().split() if w}
    c = {w for w in candidate.lower().split() if w}
    if not q or not c:
        return 0.0
    return len(q & c) / len(q)


def best_match(matches: Iterable[Match], query: str) -> Match | None:
    items = list(matches)
    if not items:
        return None
    items.sort(key=lambda m: (m.score, title_score(query, m.title)), reverse=True)
    return items[0]
