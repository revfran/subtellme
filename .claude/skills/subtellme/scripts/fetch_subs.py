#!/usr/bin/env python3
"""Orchestrator: pick subtitle sources, download, write raw .srt files.

CLI:
    python fetch_subs.py --title "Breaking Bad" --season 1 --lang en
    python fetch_subs.py --title "Dune" --year 2021 --lang es

Source chain (first hit wins):
    movie  + en  → yify     → podnapisi
    movie  + es  → subdivx  → podnapisi
    series + en  → addic7ed → podnapisi
    series + es  → subdivx  → podnapisi

The raw `.srt` files land in:
    .claude/skills/subtellme/data/<slug>/<S0X|movie>/<lang>/raw/

Stdout: the data directory path (so the skill can chain commands).
"""

from __future__ import annotations

import argparse
import logging
import re
import shutil
import sys
import unicodedata
from pathlib import Path

# Local import so this script runs from any cwd via `python fetch_subs.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sources import (  # noqa: E402
    Addic7ed,
    Match,
    Podnapisi,
    Source,
    SourceError,
    Subdivx,
    YifySubtitles,
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
    if kind == "movie" and lang == "en":
        return [YifySubtitles(), Podnapisi()]
    if kind == "movie" and lang == "es":
        return [Subdivx(), Podnapisi()]
    if kind == "series" and lang == "en":
        return [Addic7ed(), Podnapisi()]
    if kind == "series" and lang == "es":
        return [Subdivx(), Podnapisi()]
    return [Podnapisi()]


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

    if source.name == "addic7ed":
        # One Match per episode; download each.
        out: list[Path] = []
        for m in matches:
            try:
                out.extend(source.download(m, raw_dir))
            except SourceError as e:
                log.warning("addic7ed: episode %s skipped (%s)", m.extra.get("episode"), e)
        if not out:
            raise SourceError("addic7ed: no episodes downloaded")
        return out

    # Subdivx/Podnapisi: typically a single archive containing the whole season.
    pick = best_match(matches, title)
    if not pick:
        raise SourceError(f"{source.name}: ranking returned no candidate")
    log.info("[%s] best match: %s (score=%.1f)", source.name, pick.title, pick.score)
    return source.download(pick, raw_dir)


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
