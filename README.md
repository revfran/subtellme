# subtellme

A Claude Code skill that downloads subtitles for a movie or one TV season,
turns them into a plot document, and lets you ask questions about the story
with spoiler-aware answers.

## What it does

1. You point it at a title and (optionally) a season and language.
2. It scrapes subtitles from one of several public sources.
3. It parses the SRTs into clean text per episode.
4. It generates `plot.md` with sections marked as spoiler-free vs spoiler.
5. It replies with a 2-paragraph spoiler-free summary, then answers questions
   in spoiler-free mode by default. Toggle with `con spoilers` / `sin spoilers`.

## Install

The skill lives in `.claude/skills/subtellme/`. Claude Code will pick it up
automatically when this repo is the working directory (or copy the folder to
`~/.claude/skills/subtellme/` to make it available everywhere).

Python 3.10+ is required. Install dependencies once:

```
pip install -r .claude/skills/subtellme/requirements.txt
```

To extract `.rar` archives (Subdivx and a few others), the system needs the
`unrar` binary on `PATH`:

- macOS: `brew install unar` (provides `unrar`)
- Debian/Ubuntu: `sudo apt install unrar`

## Usage

Invoke from a Claude Code prompt:

- `subtellme "Breaking Bad" S01 en`
- `subtellme "Dune" 2021 es`
- `subtellme "Arrival"` (defaults to English, falls back to Spanish)

The skill will download under `.claude/skills/subtellme/data/<slug>/...`
(gitignored) and produce `plot.md` next to the episode texts.

## Sources

MVP scrapers, tried in order per language:

| Type    | English (default 1)        | Spanish (default 2) | Fallback         |
|---------|----------------------------|---------------------|------------------|
| Movie   | YIFY Subtitles             | Subdivx             | Podnapisi        |
| Series  | Addic7ed                   | Subdivx             | Podnapisi        |

Public sites change their HTML often. If a scraper breaks, the relevant file
under `scripts/sources/` is the only place that needs to be updated. Each
source has a single `search()` and `download()` function and a comment block
documenting the URLs and selectors it depends on.

## Caveats

- **Personal use only.** Respect each site's terms of service. The scrapers
  include conservative rate limits (1 req/s per host) and a realistic
  User-Agent.
- The skill caps series at one season per invocation by design.
- Subtitle quality varies. If the parser produces garbled text, try another
  language or run again to retry the next source in the chain.

## Development

The scripts are intentionally small and independent:

- `scripts/sources/*.py` — one file per scraper, all implement `Source`.
- `scripts/fetch_subs.py` — orchestrator CLI. Picks sources, validates, caches.
- `scripts/parse_srt.py` — SRT to clean episode text.
- `scripts/build_plot.py` — assembles `plot.md` using a Claude-driven prompt.

Run any script with `--help` for its CLI.
