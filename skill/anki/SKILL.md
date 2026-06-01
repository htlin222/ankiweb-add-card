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
# Nesting goes arbitrarily deep; missing parent levels are auto-created in one
# call (here both 'Spanish' and 'Spanish::Verbs' come into existence).
python3 "$SKILL/anki.py" create_deck "Spanish::Verbs"
python3 "$SKILL/anki.py" add_card "hola" "hello" -d "Spanish::Verbs" -n Basic

# Override a field by name, attach tags
python3 "$SKILL/anki.py" add_card "Q" "A" -f "Extra=a note" -t "tag1 tag2"

# Omit -d/-n to use the user's last-used deck and note type
python3 "$SKILL/anki.py" add_card "front" "back"

# Find existing notes (Anki search syntax) -> 'note_id<TAB>field-summary'
python3 "$SKILL/anki.py" search "deck:Spanish front:hola"

# Edit a card in place by note id (from `search`, or the /edit/<id> URL).
# Unspecified fields keep their current value; tags persist unless -t is given.
python3 "$SKILL/anki.py" update_card 1780339347382 -f "Front=hola (informal)"
python3 "$SKILL/anki.py" update_card 1780339347382 "new front" "new back"  # positional

# Discover available decks / note types (id<TAB>name)
python3 "$SKILL/anki.py" list-decks
python3 "$SKILL/anki.py" list-notetypes

# Rename a deck (keeps the same id and its cards). A '::' in the new name
# moves it under a parent, auto-creating the parent if needed.
python3 "$SKILL/anki.py" rename-deck "Spanish" "Español"
python3 "$SKILL/anki.py" rename-deck "Español" "Languages::Español"   # move under parent

# Remove a deck and its cards. Removing a parent also removes every subdeck
# beneath it (e.g. remove-deck "Spanish" deletes "Spanish::Verbs" too).
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

### Editing an existing card (`search` + `update_card`)

There is no "edit by content" — you edit by **note id**, which you get from
`search` (or from the AnkiWeb editor URL `ankiuser.net/edit/<note_id>`).

1. `search "<query>"` — Anki search syntax (`deck:X`, `front:Y`, `tag:Z`, or
   free text). Prints `note_id<TAB>summary` (fields joined by ` / `).
2. `update_card <note_id> …` — edits that note **in place** (same note id, no
   duplicate created).

| `update_card` flag | Meaning |
| --- | --- |
| positional `note_id` | required; numeric id from `search` |
| positional `values...` | new field values in order; **omitted trailing positions keep their current value** |
| `-f, --field NAME=VALUE` | set one field by name; repeatable — **preferred for changing a single field** |
| `-t, --tags` | replace tags; **omit to keep the note's existing tags** |

Safety notes:

- Editing only ever touches the one note you name; unspecified fields and (when
  `-t` is omitted) tags are read back and preserved, so a partial edit never
  blanks the rest of the card.
- AnkiWeb still has **no single-note delete** — `update_card` cannot remove a
  note, only change its content. To delete, you must `remove-deck` the whole
  deck (see Testing in CLAUDE.md).

## Card design — default to *short question / short answer / context below*

Unless the user asks for a different format, author cards in this shape. It
balances the two failure modes of flashcards (too granular → context-free
trivia; too dense → overloaded "leech" cards that get repeated at the pace of
their hardest part) by keeping the **recall atomic** while letting the
**understanding keep its context**.

- **Front = one focused question.** A single, irreducible concept. If you can't
  answer it in a few words, it's hiding more than one card — split it.
- **Back, line 1 = the short answer.** This is the *only* thing being tested.
  Keep it to the minimal correct response (a term, number, mechanism).
- **Back, below an `<hr>` = the context.** Explanation, mnemonic, "why", source.
  This is read *after* recalling — it deepens understanding but is **not** part
  of the graded retrieval.

```bash
# Front holds the question; Back puts the graded answer first, then context.
python3 "$SKILL/anki.py" add_card \
  "What does a positive Murphy's sign indicate?" \
  "Acute cholecystitis<hr>Inspiratory arrest on RUQ palpation due to an inflamed gallbladder contacting the examiner's hand. Sensitive but not specific; absent in many elderly/perforated cases."
```

Rules of thumb when generating cards:

- **Err toward more, smaller cards** than feels natural — but stop before the
  answer becomes a context-free fact you can't reason about. The context block
  is what prevents over-atomization.
- **If the context keeps growing**, the question is smuggling in a second
  concept — make another card instead of fattening this one.
- **Lists/enumerations are the exception**: don't make a 7-item answer and don't
  shatter it into 7 disconnected cards — use a **Cloze** note type with one
  deletion per item (`{{c1::…}} {{c2::…}}`) so each item is recalled in place.
- **Keep the answer effortful but achievable** — skip trivially easy cards;
  active recall + spaced repetition only pays off when retrieval is non-trivial
  yet succeeds.

## Usage notes

- **Resolve names, don't guess ids.** Deck and note type arguments accept the
  human name; the CLI resolves it. If the user names a deck/type you're unsure
  exists, run `list-decks` / `list-notetypes` first and pass the exact name.
- An unknown name returns a "Did you mean …?" hint — surface it to the user.
- **`rename-deck` to a name that already exists does not error** — AnkiWeb
  silently appends `+` (e.g. `Spanish` → `Spanish+`). Check `list-decks` if the
  target name might collide.
- The standard **Basic** note type takes two values: Front then Back. Other
  note types may have more fields; the CLI reports the field names on success
  and errors if too many positional values are given.
- The CLI writes to the user's real account. `create_deck`, `add_card`, and
  `remove-deck` are mutations — confirm ambiguous requests before running them.
- HTML is allowed in field values (e.g. `<b>bold</b>`, `<br>`).
