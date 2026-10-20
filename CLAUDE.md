# CLAUDE.md

Guidance for Claude Code (and humans) working in this repo.

## What this is

A tiny CLI that creates decks and adds cards on **AnkiWeb** by calling its
internal protobuf `/svc/` endpoints directly — no browser, no AnkiConnect, no
official API. Also ships as a Claude skill (`make build` → `dist/anki.skill`).

## Architecture (one file)

`skill/anki/anki.py` is the whole program. It:

- logs in via `.env` creds and caches both domain cookies (`login()`),
- hand-rolls protobuf encode/decode (`pb_*`, `_varint`) — only the wire types
  AnkiWeb uses,
- exposes `create_deck`, `rename-deck`, `add_card`, `update_card`, `search`,
  `remove-deck`, `list-decks`, `list-notetypes`, `login`.
- `--audio` (add/update) synthesizes speech — Google Translate TTS (default) or
  local Piper (`--audio-engine piper`, ffmpeg → mp3 when available, else WAV) —
  and embeds it as a `data:` URI `<audio>` tag — AnkiWeb has no media-upload endpoint, and
  `[sound:]` only plays files already synced from a desktop/mobile client.
- `--type-answer` (add/update) embeds a JS type-in widget (`TYPE_IN_*`): AnkiWeb's
  reviewer deletes `[[type:…]]`, so `{{type:Field}}` never shows a box there.
  The widget carries the typed text front→back via sessionStorage and detects
  the back by `#answer` or AnkiWeb's "Again" button (checked after a 50 ms tick,
  since AnkiWeb runs card scripts before swapping in the answer buttons).

AnkiWeb splits its API across two domains, each with its own session cookie from
one login:

| Operation | Host | Cookie `c` |
| --- | --- | --- |
| add/update/list cards & notetypes, get-note-info | `ankiuser.net` | 2 |
| create/rename/list/remove decks, **search** | `ankiweb.net` | 1 |

Login is two steps: `POST ankiweb.net/svc/account/login` → `ankiweb.net` cookie
+ an `ankiuser-login` token; then `GET ankiuser.net/account/ankiuser-login?t=…`
→ `ankiuser.net` cookie.

`/svc/editor/add-or-update` (ankiuser.net) is a `oneof mode` — it both adds and
edits. The proto (reverse-engineered from AnkiWeb's SvelteKit frontend):

```
fields  = 1 (repeated string)
tags    = 2 (string)
add     = 3 (msg {1: notetype_id, 2: deck_id})   # mode: create new note
edit    = 4 (msg {1: note_id})                   # mode: edit existing note
```

So `add_card` sends field 3 (notetype first), `update_card` sends field 4. Edit
mode replaces the note's fields, so `update_card` first calls
`/svc/editor/get-note-info` (`{1: note_id}` → `{1: values, 2: notetype_fields,
3: tags}`) to read current values/tags and preserve anything not being changed.
`search` posts `/svc/search/search` (`{1: query}`) and gets back repeated
`{1: note_id, 2: field-summary}`.

What card HTML/CSS/JS/media AnkiWeb actually renders (dark mode, images,
audio, type-in, keyboard shortcuts) is recorded in `skill/anki/SKILL.md` →
"What renders on AnkiWeb". `styles/oral-exam/` is the house card style (the
`01_血專口試快答` deck): CSS tokens for light + dark, `<details>` folding,
and a JSON → fields generator.

To check how a card really renders, log in and open `ankiuser.net/study` in
headless Chromium (Playwright, cookies from the session file), clicking the
throwaway deck on `ankiweb.net/decks`. Viewing doesn't rate cards; only the
Again/Hard/Good/Easy buttons (or keys 1–4 on the answer side) do.

## Editing

- **Single source of truth: `skill/anki/anki.py`.** Root `anki.py` is a symlink
  to it — never edit the symlink; edit the skill copy.
- `.env` (creds) and `SESSION_FILE` are resolved relative to the script, so the
  CLI works from any cwd and when packaged as a skill.

## Build & run

```bash
uv run anki.py list-decks        # run (deps via PEP 723; needs uv)
make build                       # -> dist/anki.skill (bundles .env)
make clean
```

## Testing — read this before adding test cards

The AnkiWeb web API has **no note-delete endpoint** (only `remove-deck`). To
avoid leaving residue on a real account, always test mutations on a throwaway
deck and clean up by removing the whole deck:

```bash
uv run anki.py create_deck "_tmp_test"
uv run anki.py add_card "f" "b" -d "_tmp_test"
uv run anki.py remove-deck "_tmp_test"     # deletes the deck and its cards
```

Never add test cards to an existing real deck.

## Secrets / safety

- `.env`, `cookies*.json`, `*.har`, `*.skill`, and `dist/` are gitignored — they
  hold live credentials/sessions/tokens. Never commit them or paste their values.
- The built `.skill` bundles `.env`; treat the artifact as a secret.
- These are AnkiWeb's private, undocumented endpoints — they can change without
  notice. Use only with an account you own.
