# ankiweb-cli

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)
[![Run with uv](https://img.shields.io/badge/run%20with-uv-DE5FE9.svg)](https://docs.astral.sh/uv/)
![Dependencies](https://img.shields.io/badge/deps-httpx-success.svg)
![Anki](https://img.shields.io/badge/unofficial-not%20affiliated%20with%20Anki-lightgrey.svg)

A tiny, dependency-light CLI for **AnkiWeb** that creates decks and adds cards
directly through AnkiWeb's internal protobuf `/svc/` endpoints — no browser, no
automation framework, no anti-bot bypass needed.

It logs in once with your credentials, caches both session cookies, and speaks
the same wire protocol the AnkiWeb web app uses.

## How it works

AnkiWeb splits its API across two domains, each with its own session cookie
(same login, different `c` claim):

| Operation | Domain | Cookie |
| --- | --- | --- |
| add / list cards & notetypes | `ankiuser.net` | `c:2` |
| create / list / remove decks | `ankiweb.net` | `c:1` |

A single login obtains both:

1. `POST ankiweb.net/svc/account/login` `{username, password}` → `ankiweb.net`
   cookie + an `ankiuser-login` token.
2. `GET ankiuser.net/account/ankiuser-login?t=<token>` → `ankiuser.net` cookie.

Both cookies are cached to a session file in the OS temp dir and reused until
they expire (auto-relogin on `403`). Requests and responses are length-delimited
protobuf (`Content-Type: application/octet-stream`), encoded/decoded by a small
hand-rolled codec in `anki.py`.

## Setup

Requires [`uv`](https://docs.astral.sh/uv/) (dependencies are declared inline via
PEP 723, so there's nothing to install).

Create `skill/anki/.env` with your AnkiWeb credentials (the CLI reads the `.env`
next to `anki.py`):

```dotenv
ANKI_USERID=you@example.com
ANKI_PASSWORD=your-password
```

> `.env`, the exported cookie files, and `*.har` are gitignored — they hold live
> credentials/sessions. Never commit them.

## Usage

```bash
# Decks (use :: to nest)
uv run anki.py create_deck "Spanish::Verbs"
uv run anki.py remove-deck "Spanish::Verbs"      # also removes its cards

# Cards — positional values map to the notetype's field order
uv run anki.py add_card "hola" "hello" -d "Spanish::Verbs" -n Basic

# Override a field by name, add tags
uv run anki.py add_card "Q" "A" -f "Extra=note here" -t "tag1 tag2"

# Omit -d/-n to use your last-used deck / notetype
uv run anki.py add_card "front" "back"

# Discovery
uv run anki.py list-decks          # id<TAB>name
uv run anki.py list-notetypes

# Session
uv run anki.py login               # force re-login, refresh cached session
```

### `add_card` options

| Flag | Meaning |
| --- | --- |
| positional `values...` | field values in the notetype's field order |
| `-d, --deck` | deck **name** (resolved to id) or numeric id; default: last used |
| `-n, --notetype` | notetype **name** or numeric id; default: last used |
| `-f, --field NAME=VALUE` | set a field by name (repeatable; overrides positional) |
| `-t, --tags` | space-separated tags |

Names are resolved against your collection; an unknown name produces a
"did you mean …?" suggestion. Numeric arguments are treated as raw ids.

## Claude skill

The same CLI ships as a Claude skill (for claude.ai / Claude Code). Build the
package with:

```bash
make build      # -> dist/anki.skill   (bundles anki.py + SKILL.md + .env)
make clean      # -> remove dist/
```

Upload `dist/anki.skill` in claude.ai under **Settings → Capabilities → Skills**
(the code-execution tool must be enabled). The package bundles `.env`, so it
contains your live password — keep it private and never share it.

## Layout

| Path | Purpose |
| --- | --- |
| `skill/anki/anki.py` | the CLI — single source of truth (stdlib + `httpx`) |
| `skill/anki/SKILL.md` | skill manifest (how an agent drives the CLI) |
| `skill/anki/.env` | your credentials (gitignored) |
| `anki.py` | symlink → `skill/anki/anki.py`, for `uv run anki.py` at the repo root |
| `Makefile` | `make build` → `dist/anki.skill` |
| `dist/` | build output (gitignored) |

The session cache lives in the OS temp dir (gitignored anyway), not the repo.

## Disclaimer

This talks to AnkiWeb's private, undocumented endpoints, which may change at any
time. Use it only with your own account. Not affiliated with or endorsed by Anki.
