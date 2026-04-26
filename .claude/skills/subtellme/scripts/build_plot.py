#!/usr/bin/env python3
"""Print the prompt that Claude should use to assemble `plot.md`.

This script does NOT call any LLM — the agent running this skill is
already Claude. It just bundles the template and the parsed episode
texts into a single prompt that Claude can read and act on.

Typical usage from the skill:

    python build_plot.py --data-dir <path>

Then Claude reads stdout, generates the document, and writes it back to
`<path>/plot.md` with the `Write` tool.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def gather_inputs(data_dir: Path) -> tuple[str, list[tuple[str, str]]]:
    """Return (template, [(label, text), ...]) for prompt assembly."""
    skill_root = Path(__file__).resolve().parents[1]
    template = (skill_root / "prompts" / "plot_template.md").read_text(encoding="utf-8")

    episodes_dir = data_dir / "episodes"
    movie_file = data_dir / "movie.txt"

    chunks: list[tuple[str, str]] = []
    if episodes_dir.is_dir():
        for ep in sorted(episodes_dir.glob("*.txt")):
            chunks.append((f"Episode {ep.stem}", ep.read_text(encoding="utf-8")))
    elif movie_file.is_file():
        chunks.append(("Movie", movie_file.read_text(encoding="utf-8")))
    else:
        raise SystemExit(f"no episodes/ or movie.txt under {data_dir}")
    return template, chunks


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", required=True, type=Path)
    args = p.parse_args(argv)

    template, chunks = gather_inputs(args.data_dir)

    print("# plot.md generation prompt\n")
    print("Use the template below to produce plot.md. Replace every "
          "placeholder. The 'Resumen sin spoilers' section MUST be exactly "
          "two paragraphs and reveal no twists, deaths, identities or "
          "endings — only premise, setting and tone.\n")
    print("---\n## TEMPLATE\n")
    print(template)
    print("\n---\n## SOURCE TEXT\n")
    for label, text in chunks:
        print(f"### {label}\n")
        print(text)
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
