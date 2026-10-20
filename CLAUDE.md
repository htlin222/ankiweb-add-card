# CLAUDE.md

Guidance for Claude Code (and humans) working in this repo.

## What this is

A tiny CLI that creates decks and adds/edits cards on **AnkiWeb** by calling its
internal protobuf `/svc/` endpoints directly — no browser, no AnkiConnect, no
official API. Also ships as a Claude skill (`make build` → `dist/anki.skill`).

## Layout

| Path | What |
| --- | --- |
| `skill/anki/anki.py` | the whole CLI — **single source of truth** (root `anki.py` is a symlink; never edit it) |
| `skill/anki/assets/` | CSS/JS embedded into card fields (`type-in.css`, `type-in.js`) |
| `skill/anki/SKILL.md` | skill manifest: commands, card-design rules, **What renders on AnkiWeb** |
| `tests/` | offline `unittest` suite (`make test`; CI on 3.10 + 3.13) |
| `styles/oral-exam/` | house card style (`01_血專口試快答`): CSS tokens light+dark, `<details>` folding, JSON → fields generator |
| `docs/` | background research behind the card-design rules |

Everything under `skill/anki/` ships in the skill package, so it must stay
stdlib-only and resolve files relative to `__file__` (`.env`, `assets/`). The
session cache lives in the OS temp dir.

## Architecture (`anki.py`, top to bottom)

- **Protobuf codec** — hand-rolled `pb_*` / `_varint` / `pb_decode`, only the
  wire types AnkiWeb uses.
- **Audio** (`tts_audio_html`) — Google Translate TTS (default) or local Piper
  (`--audio-engine piper`; ffmpeg → mp3 when available, else WAV), embedded as a
  `data:` URI `<audio>`. AnkiWeb has no media-upload endpoint, and `[sound:]`
  only plays files already synced from a desktop/mobile client.
- **Type-in** (`type_in_html`) — inlines `assets/type-in.{css,js}`. AnkiWeb's
  reviewer deletes `[[type:…]]`, so `{{type:Field}}` never shows a box there.
  The widget carries the typed text front→back in sessionStorage and detects
  the back by `#answer` or AnkiWeb's "Again" button, checked after a 50 ms tick
  because AnkiWeb runs card scripts before it swaps in the answer buttons.
- **HTTP + client** — stdlib urllib with a cookie jar; `AnkiWebClient` does
  login, decks, notes, search.
- **CLI** — `build_parser()` / `main()`; extra HTML (audio, type-in) goes
  through `_append_html`, and `_short` abbreviates it in printed output.

### Protocol

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

To find an endpoint, download the SvelteKit chunks (`/_app/immutable/**.mjs`)
and grep for `"/svc/`. User-facing media routes don't exist (only admin
`/svc/radmin/*`).

## Build & run

```bash
python3 anki.py list-decks       # or: uv run anki.py … (stdlib only)
make test                        # offline unit tests
make build                       # -> dist/anki.skill (bundles .env)
make preview                     # render styles/oral-exam examples (gitignored output)
```

## Testing

**Unit tests** (`tests/`) are offline: network calls are stubbed, and the
add-or-update request bodies are decoded and checked field by field. Add a test
with every change to `anki.py`, the assets, or `make_fields.py`.

**Live tests** touch a real account. The AnkiWeb web API has **no note-delete
endpoint** (only `remove-deck`), so always test mutations on a throwaway deck
and clean up by removing the whole deck:

```bash
python3 anki.py create_deck "_tmp_test"
python3 anki.py add_card "f" "b" -d "_tmp_test"
python3 anki.py remove-deck "_tmp_test"     # deletes the deck and its cards
```

Never add test cards to an existing real deck.

To check how a card really renders, open `ankiuser.net/study` in headless
Chromium (Playwright, cookies from the session file) by clicking the throwaway
deck on `ankiweb.net/decks`. Viewing doesn't rate cards; only the
Again/Hard/Good/Easy buttons (or keys 1–4 on the answer side) do. Record new
rendering findings in SKILL.md → "What renders on AnkiWeb".

## Secrets / safety

- `.env`, `cookies*.json`, `*.har`, `*.skill`, and `dist/` are gitignored — they
  hold live credentials/sessions/tokens. Never commit them or paste their values.
- The built `.skill` bundles `.env`; treat the artifact as a secret.
- These are AnkiWeb's private, undocumented endpoints — they can change without
  notice. Use only with an account you own.
