# Q&A rules for the `subtellme` skill

These rules apply once `plot.md` exists. Follow them strictly.

## 1. Modes

There are exactly two modes:

- **no-spoilers** (default for every new conversation about a title).
- **spoilers**.

Track the current mode for the active title. The mode is reset to
`no-spoilers` whenever the user asks about a different title.

### Switching mode

Switch to **spoilers** when the user says any of:

- "con spoilers", "modo spoiler", "spoilers on", "activa spoilers"
- "spoilers please", "with spoilers", "spoiler mode", "spoil me"

Switch back to **no-spoilers** when the user says any of:

- "sin spoilers", "spoilers off", "no spoilers", "desactiva spoilers"

When the mode changes, confirm in **one short sentence** in the user's
language. Examples:

- "Modo spoilers activado."
- "Spoilers off — back to safe answers."

## 2. Source of truth per mode

- In **no-spoilers** mode you may ONLY use:
  - The sections of `plot.md` *before* the line `<!-- SPOILERS BELOW -->`.
  - General world knowledge that does not reveal story specifics.
- In **spoilers** mode you may use:
  - The full `plot.md`.
  - The episode/movie text files under `episodes/` or `movie.txt`.

Never quote from the spoiler sections while in `no-spoilers` mode, even
indirectly via paraphrase.

## 3. Refusing gracefully

If a user asks something in `no-spoilers` mode that cannot be answered
truthfully without spoilers, do **not** make up a sanitised answer.
Reply with one short paragraph along the lines of:

> Eso entra en territorio de spoilers — si quieres saberlo, dime
> "con spoilers" y te lo cuento.

(Match the user's language.)

Never:
- Hint at twists with winks ("you'll see…", "let's just say…").
- Confirm or deny whether a character dies, betrays, is secretly someone,
  etc., while in `no-spoilers` mode. Treat any such yes/no as a spoiler.

## 4. Honest uncertainty

Subtitles miss visual information. If the user asks about something the
subtitle text cannot ground (a costume, a face, an unspoken glance),
say you cannot tell from the dialogue alone.

## 5. Style

- Match the user's language (es / en).
- Keep answers tight: 1–4 short paragraphs unless the user asks for more.
- Cite episodes when relevant: "(S01E04)".
- Avoid meta commentary about being an AI.
