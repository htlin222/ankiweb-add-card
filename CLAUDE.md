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
