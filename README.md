# subtellme

A Claude Code skill that downloads subtitles for a movie or one TV season,
turns them into a plot document, and lets you ask questions about the story
with spoiler-aware answers.

## What it does

1. You point it at a title and (optionally) a season and language.
2. It downloads subtitles from OpenSubtitles.com.
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

Copy `.env.example` to `.env` and fill in your OpenSubtitles.com credentials:

```
cp .env.example .env
# Then edit .env with your API key, username, and password
```

Get an API key at https://www.opensubtitles.com/en/consumers (free tier
allows 5 subtitle downloads per day).

## Usage

Invoke from a Claude Code prompt:

- `subtellme "Breaking Bad" S01 en`
- `subtellme "Dune" 2021 es`
- `subtellme "Arrival"` (defaults to English, falls back to Spanish)

The skill will download under `.claude/skills/subtellme/data/<slug>/...`
(gitignored) and produce `plot.md` next to the episode texts.

## Sources

**OpenSubtitles.com** is the sole subtitle source. It requires an API key
(see Install). The free tier allows 5 downloads per day.

Each source is a single file under `scripts/sources/` implementing `Source`
with `search()` and `download()` methods.

## Caveats

- **Personal use only.** Respect OpenSubtitles.com's terms of service. The
  free tier is limited to 5 downloads/day.
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
