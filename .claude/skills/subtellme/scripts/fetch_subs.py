#!/usr/bin/env python3
"""Orchestrator: pick subtitle sources, download, write raw .srt files.

CLI:
    python fetch_subs.py --title "Breaking Bad" --season 1 --lang en
    python fetch_subs.py --title "Dune" --year 2021 --lang es

Source: OpenSubtitles.com API (requires API key in .env).

The raw `.srt` files land in:
    .claude/skills/subtellme/data/<slug>/<S0X|movie>/<lang>/raw/

Stdout: the data directory path (so the skill can chain commands).
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import sys
import unicodedata
from pathlib import Path


def _load_dotenv() -> None:
    """Load .env from the repo root (4 levels up from this script)."""
    env_file = Path(__file__).resolve().parents[4] / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if key and value and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

# Local import so this script runs from any cwd via `python fetch_subs.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sources import (  # noqa: E402
    Match,
    OpenSubtitles,
    Source,
    SourceError,
)
from sources.base import best_match  # noqa: E402

log = logging.getLogger("subtellme.fetch")


def slugify(text: str) -> str:
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    norm = re.sub(r"[^a-zA-Z0-9]+", "-", norm).strip("-").lower()
    return norm or "untitled"


def data_root() -> Path:
    return Path(__file__).resolve().parents[1] / "data"


def resolve_target_dir(title: str, season: int | None, lang: str) -> Path:
    bucket = f"S{season:02d}" if season is not None else "movie"
    return data_root() / slugify(title) / bucket / lang


def chain_for(kind: str, lang: str) -> list[Source]:
    return [OpenSubtitles()]


def fetch_movie(source: Source, title: str, year: int | None, lang: str,
                raw_dir: Path) -> list[Path]:
    matches = source.search(title, lang, year=year)
    pick = best_match(matches, title)
    if not pick:
        raise SourceError(f"{source.name}: no match for '{title}'")
    log.info("[%s] best match: %s (score=%.1f)", source.name, pick.title, pick.score)
    return source.download(pick, raw_dir)


def fetch_series(source: Source, title: str, season: int, lang: str,
                 raw_dir: Path) -> list[Path]:
    matches = source.search(title, lang, season=season)
    if not matches:
        raise SourceError(f"{source.name}: no episodes for '{title}' S{season:02d}")

    # Group by episode; download the best match per episode.
    by_episode: dict[int, list[Match]] = {}
    for m in matches:
        ep = m.extra.get("episode", 0)
        by_episode.setdefault(ep, []).append(m)

    if by_episode and all(ep == 0 for ep in by_episode):
        # No episode info — just download the top match.
        pick = best_match(matches, title)
        if not pick:
            raise SourceError(f"{source.name}: ranking returned no candidate")
        log.info("[%s] best match: %s (score=%.1f)", source.name, pick.title, pick.score)
        return source.download(pick, raw_dir)

    # Download per episode.
    out: list[Path] = []
    for ep in sorted(by_episode):
        if ep == 0:
            continue
        pick = best_match(by_episode[ep], title)
        if not pick:
            continue
        try:
            out.extend(source.download(pick, raw_dir))
        except SourceError as e:
            log.warning("%s: episode %d skipped (%s)", source.name, ep, e)
    if not out:
        raise SourceError(f"{source.name}: no episodes downloaded")
    return out


def run(title: str, season: int | None, year: int | None, lang: str,
        force: bool) -> Path:
    if season is not None and season < 1:
        raise SystemExit("--season must be >= 1")
    kind = "series" if season is not None else "movie"

    target = resolve_target_dir(title, season, lang)
    raw_dir = target / "raw"
    if raw_dir.is_dir() and any(raw_dir.glob("*.srt")) and not force:
        log.info("already downloaded → %s", target)
        return target
    if force and raw_dir.is_dir():
        shutil.rmtree(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)

    last_err: Exception | None = None
    for source in chain_for(kind, lang):
        log.info("trying source %s …", source.name)
        try:
            files = (fetch_series(source, title, season, lang, raw_dir)
                     if kind == "series"
                     else fetch_movie(source, title, year, lang, raw_dir))
        except SourceError as e:
            log.warning("%s failed: %s", source.name, e)
            last_err = e
            continue
        if files:
            log.info("got %d file(s) from %s", len(files), source.name)
            return target

    if raw_dir.exists() and not any(raw_dir.iterdir()):
        raw_dir.rmdir()
    raise SystemExit(f"all sources failed; last error: {last_err}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--title", required=True)
    p.add_argument("--year", type=int)
    p.add_argument("--season", type=int, help="single season number; max 1 per run")
    p.add_argument("--lang", default="en", choices=("en", "es"))
    p.add_argument("--force", action="store_true",
                   help="re-download even if raw/ already has .srt files")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    target = run(args.title, args.season, args.year, args.lang, args.force)
    print(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
