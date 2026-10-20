# ankiweb-cli

[![test](https://github.com/htlin222/ankiweb-add-card/actions/workflows/test.yml/badge.svg)](https://github.com/htlin222/ankiweb-add-card/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
![Dependencies](https://img.shields.io/badge/deps-none%20(stdlib)-success.svg)
![Anki](https://img.shields.io/badge/unofficial-not%20affiliated%20with%20Anki-lightgrey.svg)

A tiny, dependency-free CLI for **AnkiWeb**: create, rename and remove decks;
add, search and edit cards — directly through AnkiWeb's internal protobuf
`/svc/` endpoints. No browser, no AnkiConnect, no desktop app.

It also makes cards richer than the AnkiWeb editor allows:

- **Pronunciation** (`--audio`) — TTS embedded in the card, from Google or a
  local [Piper](https://github.com/rhasspy/piper) voice. AnkiWeb has no media
  upload; this needs none.
- **Type-in answers** (`--type-answer`) — AnkiWeb silently drops
  `{{type:Field}}`; this embeds a working input with a letter-by-letter diff.
- **Any HTML/CSS/JS** in fields — tested on AnkiWeb, including dark mode,
  images without upload, and `<details>` folding. See
  [What renders on AnkiWeb](skill/anki/SKILL.md#what-renders-on-ankiweb-tested-in-its-study-view).

Ships as a Claude skill too, so an agent can manage your cards.

## Setup

Python 3.10+, standard library only. Create `skill/anki/.env` (gitignored):

```dotenv
ANKI_USERID=you@example.com
ANKI_PASSWORD=your-password
```

Run with `python3 anki.py …` or `uv run anki.py …` from the repo root (`anki.py`
is a symlink to `skill/anki/anki.py`). Login happens on first use and the
session is cached in the OS temp dir.

Optional: `pip install piper-tts` for offline TTS, and `ffmpeg` to store it as
mp3 (≈6× smaller than WAV).

## Usage

```bash
# Decks ('::' nests; missing parents are created)
python3 anki.py create_deck "Spanish::Verbs"
python3 anki.py rename-deck "Spanish" "Languages::Spanish"
python3 anki.py remove-deck "Spanish::Verbs"     # also removes its cards
python3 anki.py list-decks                      # id<TAB>name
python3 anki.py list-notetypes

# Cards — positional values fill the note type's fields in order
python3 anki.py add_card "hola" "hello" -d "Spanish::Verbs" -n Basic
python3 anki.py add_card "Q" "A" -f "Extra=note here" -t "tag1 tag2"

# Find and edit in place (unspecified fields and tags are preserved)
python3 anki.py search "deck:Spanish front:hola"   # note_id<TAB>summary
python3 anki.py update_card 1780339347382 -f "Back=hello (informal)"

# Pronunciation and type-in answers (also on update_card)
python3 anki.py add_card "tag" "標籤" -a "tag"
python3 anki.py add_card "tag" "標籤" -a "tag" --audio-engine piper
python3 anki.py add_card "FAB type?" "acute promyelocytic leukemia" \
  --type-answer "acute promyelocytic leukemia|APL"
```

### Options (`add_card`; `update_card` takes the same except `-d`/`-n`)

| Flag | Meaning |
| --- | --- |
| `values...` | field values in the note type's field order |
| `-d, --deck` / `-n, --notetype` | name or numeric id; default: last used. Unknown names get a "did you mean …?" hint |
| `-f, --field NAME=VALUE` | set a field by name (repeatable; overrides positional) |
| `-t, --tags` | space-separated tags (`update_card`: replaces; omit to keep) |
| `-a, --audio TEXT` | append a spoken `<audio>` player for TEXT (repeatable) |
| `--audio-lang` | `en` (default), `en-GB`, `ja`, `zh-TW`, … |
| `--audio-engine` | `google` (online, ≤200 chars; default) or `piper` (local). Default from `$ANKI_AUDIO_ENGINE` |
| `--audio-voice` | Piper voice; defaults by language (`en_US-lessac-medium`, `en_GB-alba-medium`, `zh_CN-huayan-medium`). Voices download to `$PIPER_DATA_DIR` (default `~/.local/share/piper`) |
| `--type-answer ANSWER` | append a type-in box; `\|` separates accepted answers. Enter reveals; the back shows a case-insensitive diff |
| `--audio-field` / `--type-field NAME` | field to append to (default: first field) |

## How it works

AnkiWeb splits its API across two domains, each with its own session cookie
from the same login:

| Operation | Domain |
| --- | --- |
| add / update / read notes, list note types | `ankiuser.net` |
| create / rename / remove / list decks, search | `ankiweb.net` |

1. `POST ankiweb.net/svc/account/login` → `ankiweb.net` cookie + an
   `ankiuser-login` token.
2. `GET ankiuser.net/account/ankiuser-login?t=<token>` → `ankiuser.net` cookie.

Bodies are protobuf (`application/octet-stream`), encoded by a small hand-rolled
codec. Adding and editing share one endpoint, `/svc/editor/add-or-update`, whose
`oneof` picks *add* (note type + deck) or *edit* (note id). Protocol notes for
contributors are in [CLAUDE.md](CLAUDE.md).

## Claude skill

```bash
make build      # -> dist/anki.skill (anki.py + assets/ + SKILL.md + .env)
make link       # or: symlink into ~/.claude/skills for Claude Code
```

Upload `dist/anki.skill` in claude.ai under **Settings → Capabilities → Skills**.
It contains your `.env`, i.e. your password — keep it private.

## Card styles and design notes

- [`styles/oral-exam/`](styles/oral-exam/) — a complete house style (CSS tokens
  for light + dark, templates, `<details>` folding) with a JSON → fields
  generator. `make preview` renders its examples.
- [`docs/flashcard-design-research.md`](docs/flashcard-design-research.md) —
  the evidence behind the card-design rules in `SKILL.md`.

## Development

```bash
make test       # offline unit tests (no account or network needed)
```

| Path | Purpose |
| --- | --- |
| `skill/anki/anki.py` | the CLI — single source of truth |
| `skill/anki/assets/` | CSS/JS embedded into cards (type-in widget) |
| `skill/anki/SKILL.md` | skill manifest + card-authoring guide for agents |
| `tests/` | `unittest` suite, run in CI on Python 3.10 and 3.13 |
| `styles/`, `docs/` | card styles and background research |

Test anything that writes to AnkiWeb on a throwaway deck (`_tmp_test`) and
remove it afterwards — the API has no single-note delete. See
[CLAUDE.md](CLAUDE.md) for the protocol and testing conventions.

## Disclaimer

This talks to AnkiWeb's private, undocumented endpoints, which may change at any
time. Use it only with your own account. Not affiliated with or endorsed by Anki.
