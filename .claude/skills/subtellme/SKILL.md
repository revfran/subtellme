---
name: subtellme
description: |
  Download subtitles for a movie or one TV season, build a plot document
  from them, and answer questions about the story with spoiler-aware
  responses. Default language is English, falling back to Spanish.
  Use whenever the user asks about a movie or series and wants a synopsis,
  a spoiler-free recap, or to ask plot questions.
triggers:
  - "subtellme"
  - "trama de"
  - "resumen sin spoilers de"
  - "spoiler-free summary of"
---

# subtellme

You are running the `subtellme` skill. The user wants to either build a
plot document for a title or ask questions about one already built.

## Inputs to extract from the user

- **Title** (required). A movie or TV series.
- **Year** (optional, helps disambiguate movies).
- **Season** (only for series, max 1, e.g. `S01`). Reject >1 season.
- **Language**: `en` or `es`. Default `en` with `es` as fallback.

If any of these are ambiguous (e.g. multiple movies with the same title),
ask **one** clarifying question before downloading.

## Workflow

### A. First time for a title — build the plot

1. Compute a slug: lowercased title, ASCII-only, spaces → `-`.
   Data path: `.claude/skills/subtellme/data/<slug>/<S0X|movie>/<lang>/`.
2. If `plot.md` already exists at that path, skip to step 7.
3. Run the orchestrator:
   ```
   python .claude/skills/subtellme/scripts/fetch_subs.py \
     --title "<title>" [--year YYYY] [--season N] --lang <en|es>
   ```
   It tries the source chain (YIFY/Addic7ed → Subdivx → Podnapisi) and
   writes raw `.srt` files under `raw/`.
4. Parse them:
   ```
   python .claude/skills/subtellme/scripts/parse_srt.py \
     --data-dir <data_path>
   ```
   Produces `episodes/<NN>.txt` (or `movie.txt`).
5. Build the plot document. Read the episode text(s) yourself (with the
   `Read` tool — do not stream them through `cat`) and the template at
   `prompts/plot_template.md`. Generate `plot.md` filling **every**
   section. Crucial:
   - The "Resumen sin spoilers" section must be exactly two paragraphs
     and reveal **no** plot twist, character death, identity reveal, or
     ending detail. It tells the reader the premise and tone, nothing else.
   - Sections after `<!-- SPOILERS BELOW -->` may contain anything.
6. Write `plot.md` to the data path with the `Write` tool.
7. Reply to the user with **only** the two-paragraph spoiler-free summary,
   followed by a single short line: "Pregúntame lo que quieras. Por
   defecto respondo sin spoilers; di `con spoilers` para activarlos."
   (English equivalent if the user is writing in English.)

### B. Follow-up questions — answer with spoiler awareness

Read `prompts/qa_system.md` and follow it. In short:

- Track a session mode. Default: `no-spoilers`. Switch on phrases like
  "con spoilers", "modo spoiler on", "spoilers please", "sin spoilers",
  "no spoilers". Confirm the switch in one short sentence.
- In `no-spoilers` mode, only use content from the spoiler-free section
  of `plot.md`. If a faithful answer would require spoilers, say so and
  invite the user to switch modes.
- In `spoilers` mode, use the entire `plot.md` and the episode texts.

## Hard rules

- **Never** download more than one season per invocation. If the user
  asks for "all seasons", explain the limit and ask which one to start
  with.
- **Never** commit anything under `data/` to git (it is gitignored).
- **Never** invent plot details. If the subtitles do not contain a fact,
  say you do not know rather than guess.
- If a scraper fails, the orchestrator falls through to the next source.
  If the whole chain fails, surface the last error to the user verbatim
  and suggest checking title/year/language.

## Files in this skill

- `scripts/fetch_subs.py` — orchestrator CLI.
- `scripts/sources/` — one scraper per source, same interface.
- `scripts/parse_srt.py` — SRT → clean episode text.
- `scripts/build_plot.py` — optional helper that prints the prompt to
  build `plot.md` (you can also assemble it inline using the template).
- `prompts/plot_template.md` — structure of `plot.md`.
- `prompts/qa_system.md` — spoiler-aware Q&A rules.
