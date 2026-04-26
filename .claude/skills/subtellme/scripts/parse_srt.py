#!/usr/bin/env python3
"""Convert SRT files into clean episode/movie text.

Input: a data directory created by `fetch_subs.py`, with `raw/*.srt`.
Output: `episodes/<NN>.txt` (series) or `movie.txt` (movie). One paragraph
per dialogue block, blank line between blocks, no timestamps or HTML tags.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

log = logging.getLogger("subtellme.parse")

TAG_RE = re.compile(r"<[^>]+>")
BRACKET_RE = re.compile(r"\[[^\]]+\]")  # [music], [door creaks]
SPEAKER_RE = re.compile(r"^[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ '\.\-]{1,30}:\s*")
INDEX_RE = re.compile(r"^\d+\s*$")
TIME_RE = re.compile(r"\d{2}:\d{2}:\d{2}[,\.]\d{3}\s*-->")


def clean_srt(text: str) -> str:
    """Return a clean paragraph stream from SRT content."""
    blocks: list[str] = []
    current: list[str] = []

    for raw in text.splitlines():
        line = raw.strip("﻿").rstrip()
        if not line:
            if current:
                blocks.append(" ".join(current))
                current = []
            continue
        if INDEX_RE.match(line):
            continue
        if TIME_RE.search(line):
            continue
        line = TAG_RE.sub("", line)
        line = BRACKET_RE.sub("", line)
        line = SPEAKER_RE.sub("", line)
        line = line.replace("​", "").strip()
        if line.startswith("- "):
            line = line[2:]
        if line:
            current.append(line)
    if current:
        blocks.append(" ".join(current))

    # Collapse whitespace and empties; drop near-duplicate consecutive blocks.
    deduped: list[str] = []
    last = ""
    for b in blocks:
        b = re.sub(r"\s+", " ", b).strip()
        if not b or b == last:
            continue
        deduped.append(b)
        last = b
    return "\n\n".join(deduped) + "\n"


def read_srt(path: Path) -> str:
    """Read an .srt file with the most common encodings."""
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("srt", b"", 0, 1, f"could not decode {path}")


def episode_number(filename: str) -> int | None:
    """Best-effort: pull an episode number from common naming patterns."""
    m = re.search(r"[Ss]\d{1,2}[Ee](\d{1,3})", filename)
    if m:
        return int(m.group(1))
    m = re.search(r"(?:^|[^0-9])(\d{1,3})(?:[^0-9]|$)", Path(filename).stem)
    if m:
        return int(m.group(1))
    return None


def parse_directory(data_dir: Path) -> list[Path]:
    raw_dir = data_dir / "raw"
    if not raw_dir.is_dir():
        raise SystemExit(f"no raw/ directory under {data_dir}")
    srts = sorted(raw_dir.glob("*.srt"))
    if not srts:
        raise SystemExit(f"no .srt files under {raw_dir}")

    is_series = (data_dir.parent.name.lower().startswith("s")
                 and data_dir.parent.name[1:].isdigit())

    written: list[Path] = []
    if is_series or len(srts) > 1:
        out_dir = data_dir / "episodes"
        out_dir.mkdir(exist_ok=True)
        for srt in srts:
            ep = episode_number(srt.name)
            label = f"{ep:02d}" if ep is not None else srt.stem
            target = out_dir / f"{label}.txt"
            target.write_text(clean_srt(read_srt(srt)), encoding="utf-8")
            log.info("wrote %s", target)
            written.append(target)
    else:
        target = data_dir / "movie.txt"
        target.write_text(clean_srt(read_srt(srts[0])), encoding="utf-8")
        log.info("wrote %s", target)
        written.append(target)

    return written


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", required=True, type=Path,
                   help="directory created by fetch_subs.py")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )
    written = parse_directory(args.data_dir)
    print("\n".join(str(p) for p in written))
    return 0


if __name__ == "__main__":
    sys.exit(main())
