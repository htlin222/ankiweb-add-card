---
name: anki
description: >-
  Create decks and add cards/flashcards to the user's AnkiWeb account from the
  command line. Bundles a self-contained Python CLI plus the user's AnkiWeb
  credentials, so no setup is required. Use whenever the user wants to add a
  flashcard or note to Anki/AnkiWeb, create or remove an Anki deck, or list
  their existing Anki decks or note types — e.g. "add a card to my Spanish
  deck", "make an Anki deck called X", "save this as a flashcard".
---

# Anki

Add cards and create decks on the user's AnkiWeb account. A bundled CLI
(`anki.py`) logs in with the bundled `.env` credentials, caches the session,
and calls AnkiWeb's internal endpoints directly. No browser, no extra config.

## Running the CLI

The skill is installed at a runtime path shown as **"Base directory for this
skill"**. Always invoke the CLI by absolute path from that base directory:

```bash
SKILL="<the base directory for this skill>"
python3 "$SKILL/anki.py" <command> [args]
```

The CLI is pure Python stdlib — no dependencies, no install step.

Login happens automatically on the first command and is cached; don't run
`login` unless a command fails with an auth error.

## Commands

```bash
# Typical flow: make a new deck ('::' nests subdecks), then add a card to it.
# Positional values fill the note type's fields IN ORDER.
python3 "$SKILL/anki.py" create_deck "Spanish::Verbs"
python3 "$SKILL/anki.py" add_card "hola" "hello" -d "Spanish::Verbs" -n Basic

# Override a field by name, attach tags
python3 "$SKILL/anki.py" add_card "Q" "A" -f "Extra=a note" -t "tag1 tag2"

# Omit -d/-n to use the user's last-used deck and note type
python3 "$SKILL/anki.py" add_card "front" "back"

# Discover available decks / note types (id<TAB>name)
python3 "$SKILL/anki.py" list-decks
python3 "$SKILL/anki.py" list-notetypes

# Remove a deck and its cards
python3 "$SKILL/anki.py" remove-deck "Spanish::Verbs"
```

### `add_card` flags

| Flag | Meaning |
| --- | --- |
| positional `values...` | field values in the note type's field order (commonly Front, Back) |
| `-d, --deck` | deck name (resolved to id) or numeric id; default: last used |
| `-n, --notetype` | note type name or numeric id; default: last used |
| `-f, --field NAME=VALUE` | set a field by name; repeatable; overrides positional |
| `-t, --tags` | space-separated tags |

## Usage notes

- **Resolve names, don't guess ids.** Deck and note type arguments accept the
  human name; the CLI resolves it. If the user names a deck/type you're unsure
  exists, run `list-decks` / `list-notetypes` first and pass the exact name.
- An unknown name returns a "Did you mean …?" hint — surface it to the user.
- The standard **Basic** note type takes two values: Front then Back. Other
  note types may have more fields; the CLI reports the field names on success
  and errors if too many positional values are given.
- The CLI writes to the user's real account. `create_deck`, `add_card`, and
  `remove-deck` are mutations — confirm ambiguous requests before running them.
- HTML is allowed in field values (e.g. `<b>bold</b>`, `<br>`).
