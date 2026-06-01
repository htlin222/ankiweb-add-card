#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""Minimal AnkiWeb CLI: create decks, add/search/edit cards.

Logs in once with credentials from the .env next to this script, caches both
domain session cookies, and talks to AnkiWeb's protobuf `/svc/` endpoints
directly (no browser). Pure stdlib — no third-party deps, so `python3 anki.py
<command>` runs in any Python 3.10+ environment with no install step.
"""
from __future__ import annotations

import argparse
import gzip
import http.cookiejar
import json
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from pathlib import Path

ANKIWEB = "https://ankiweb.net"
ANKIUSER = "https://ankiuser.net"
# Resolve .env relative to this script (skills run from an arbitrary cwd).
ENV_FILE = Path(__file__).resolve().parent / ".env"
# Cache the session in a writable temp dir (the skill dir may be read-only).
SESSION_FILE = Path(tempfile.gettempdir()) / "anki_session.json"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
)


# --------------------------------------------------------------------------- #
# Minimal protobuf encode/decode (only the wire types AnkiWeb uses)
# --------------------------------------------------------------------------- #
def _varint(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _read_varint(data: bytes, i: int) -> tuple[int, int]:
    v = shift = 0
    while True:
        b = data[i]
        i += 1
        v |= (b & 0x7F) << shift
        if not b & 0x80:
            return v, i
        shift += 7


def _tag(field: int, wt: int) -> bytes:
    return _varint((field << 3) | wt)


def pb_string(field: int, s: str) -> bytes:
    b = s.encode()
    return _tag(field, 2) + _varint(len(b)) + b


def pb_int(field: int, n: int) -> bytes:
    return _tag(field, 0) + _varint(n)


def pb_message(field: int, payload: bytes) -> bytes:
    return _tag(field, 2) + _varint(len(payload)) + payload


def pb_decode(data: bytes) -> dict[int, list]:
    """Decode bytes into {field_no: [values]} (varint->int, len-delim->bytes)."""
    out: dict[int, list] = {}
    i = 0
    while i < len(data):
        tag, i = _read_varint(data, i)
        fno, wt = tag >> 3, tag & 7
        if wt == 0:
            v, i = _read_varint(data, i)
        elif wt == 2:
            ln, i = _read_varint(data, i)
            v, i = data[i : i + ln], i + ln
        elif wt == 5:
            v, i = data[i : i + 4], i + 4
        elif wt == 1:
            v, i = data[i : i + 8], i + 8
        else:
            raise ValueError(f"unsupported wire type {wt} at offset {i}")
        out.setdefault(fno, []).append(v)
    return out


def _as_str(v: bytes) -> str:
    return v.decode(errors="replace") if isinstance(v, (bytes, bytearray)) else str(v)


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #
class AnkiError(Exception):
    pass


# --------------------------------------------------------------------------- #
# Tiny stdlib HTTP layer (httpx-shaped, so the client code below is unchanged).
# Backed by urllib + a cookie jar; no third-party deps means no install step.
# --------------------------------------------------------------------------- #
class _Response:
    def __init__(self, status_code: int, content: bytes) -> None:
        self.status_code = status_code
        self.content = content

    @property
    def text(self) -> str:
        return self.content.decode(errors="replace")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise AnkiError(f"HTTP {self.status_code}: {self.text[:200]}")


class _Cookies:
    """Adapter over http.cookiejar exposing the bits AnkiWebClient touches."""

    def __init__(self, jar: http.cookiejar.CookieJar) -> None:
        self.jar = jar

    def set(self, name: str, value: str, domain: str, path: str = "/") -> None:
        dot = domain.startswith(".")
        self.jar.set_cookie(http.cookiejar.Cookie(
            version=0, name=name, value=value, port=None, port_specified=False,
            domain=domain, domain_specified=dot, domain_initial_dot=dot,
            path=path, path_specified=True, secure=True, expires=None,
            discard=False, comment=None, comment_url=None, rest={}, rfc2109=False,
        ))


class _HttpClient:
    """Minimal httpx.Client stand-in over urllib (cookies, POST/GET, redirects)."""

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout
        self.cookies = _Cookies(http.cookiejar.CookieJar())
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies.jar)
        )

    def _request(self, method: str, url: str, *, content=None, headers=None) -> _Response:
        req = urllib.request.Request(url, data=content, method=method)
        req.add_header("User-Agent", UA)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            resp = self._opener.open(req, timeout=self.timeout)
            raw, status, enc = resp.read(), resp.status, resp.headers.get("Content-Encoding", "")
        except urllib.error.HTTPError as e:  # 4xx/5xx are responses here, not errors
            raw, status, enc = e.read(), e.code, e.headers.get("Content-Encoding", "")
        enc = (enc or "").lower()
        if enc == "gzip":
            raw = gzip.decompress(raw)
        elif enc == "deflate":
            raw = zlib.decompress(raw)
        return _Response(status, raw)

    def post(self, url: str, *, content: bytes = b"", headers=None) -> _Response:
        return self._request("POST", url, content=content, headers=headers)

    def get(self, url: str, *, params=None, headers=None, follow_redirects: bool = True) -> _Response:
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        return self._request("GET", url, headers=headers)  # urllib follows redirects


class AnkiWebClient:
    LOGIN_STATUS = {0: "UNKNOWN", 1: "AUTHENTICATED", 2: "INVALID_USER", 3: "INVALID_PASS"}

    def __init__(self) -> None:
        self.client = _HttpClient(timeout=30)
        self._load_session()

    # ---- session persistence ------------------------------------------------
    def _load_session(self) -> None:
        if not SESSION_FILE.exists():
            return
        try:
            data = json.loads(SESSION_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return
        for c in data.get("cookies", []):
            self.client.cookies.set(c["name"], c["value"], domain=c["domain"], path="/")

    def _save_session(self) -> None:
        cookies = [
            {"name": c.name, "value": c.value, "domain": c.domain}
            for c in self.client.cookies.jar
            if c.name in ("ankiweb", "has_auth")
        ]
        try:
            SESSION_FILE.write_text(json.dumps({"cookies": cookies, "saved_at": int(time.time())}))
            SESSION_FILE.chmod(0o600)
        except OSError:
            pass  # caching is best-effort

    def _has_cookie(self, domain: str) -> bool:
        return any(c.name == "ankiweb" and domain in c.domain for c in self.client.cookies.jar)

    def ensure_login(self, force: bool = False) -> None:
        if force or not (self._has_cookie("ankiweb.net") and self._has_cookie("ankiuser.net")):
            self.login()

    # ---- login --------------------------------------------------------------
    @staticmethod
    def _read_creds() -> tuple[str, str]:
        if not ENV_FILE.exists():
            raise AnkiError(f"{ENV_FILE} not found (need ANKI_USERID and ANKI_PASSWORD)")
        env: dict[str, str] = {}
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
        try:
            return env["ANKI_USERID"], env["ANKI_PASSWORD"]
        except KeyError as e:
            raise AnkiError(f"missing {e} in .env") from None

    def login(self) -> None:
        user, pw = self._read_creds()
        # step 1: authenticate on ankiweb.net -> sets ankiweb.net cookie (c:1)
        r = self.client.post(
            f"{ANKIWEB}/svc/account/login",
            content=pb_string(1, user) + pb_string(2, pw),
            headers={"Content-Type": "application/octet-stream", "Origin": ANKIWEB,
                     "Referer": f"{ANKIWEB}/account/login"},
        )
        r.raise_for_status()
        fields = pb_decode(r.content)
        status = fields.get(1, [0])[0]
        if status != 1:
            raise AnkiError(f"login failed: {self.LOGIN_STATUS.get(status, status)}")
        token = _as_str(fields[2][0])
        # step 2: redeem the ankiuser-login token -> sets ankiuser.net cookie (c:2)
        self.client.get(
            f"{ANKIUSER}/account/ankiuser-login", params={"t": token}, follow_redirects=True
        ).raise_for_status()
        self._save_session()

    # ---- transport ----------------------------------------------------------
    def _svc(self, base: str, path: str, body: bytes = b"", *, retry: bool = True) -> bytes:
        r = self.client.post(
            f"{base}{path}",
            content=body,
            headers={"Content-Type": "application/octet-stream", "Origin": base,
                     "Referer": f"{base}/"},
        )
        if r.status_code == 403 and retry:  # session expired -> relogin once
            self.login()
            return self._svc(base, path, body, retry=False)
        if r.status_code != 200:
            raise AnkiError(f"{path} -> HTTP {r.status_code}: {r.text[:200]}")
        return r.content

    # ---- editor (ankiuser.net) ----------------------------------------------
    @staticmethod
    def _id_name(raw: bytes) -> tuple[int, str]:
        m = pb_decode(raw)
        return m.get(1, [0])[0], _as_str(m.get(2, [b""])[0])

    @staticmethod
    def _field_names(entries: list[bytes]) -> list[str]:
        # each entry is a Field message; field #2 is the name
        return [_as_str(pb_decode(e).get(2, [b""])[0]) for e in entries]

    def get_info_for_adding(self) -> dict:
        self.ensure_login()
        d = pb_decode(self._svc(ANKIUSER, "/svc/editor/get-info-for-adding"))
        return {
            "notetypes": [self._id_name(x) for x in d.get(1, [])],
            "decks": [self._id_name(x) for x in d.get(2, [])],
            "current_deck_id": d.get(3, [None])[0],
            "current_notetype_id": d.get(4, [None])[0],
            "current_fields": self._field_names(d.get(5, [])),
        }

    def get_notetype_fields(self, notetype_id: int) -> list[str]:
        d = pb_decode(self._svc(ANKIUSER, "/svc/editor/get-notetype-fields", pb_int(1, notetype_id)))
        return self._field_names(d.get(1, []))

    def add_card(self, deck=None, notetype=None, values=(), named=None, tags="") -> dict:
        info = self.get_info_for_adding()
        deck_id = self._resolve(deck, info["decks"], "deck") if deck else info["current_deck_id"]
        notetype_id = (
            self._resolve(notetype, info["notetypes"], "notetype") if notetype
            else info["current_notetype_id"]
        )
        if deck_id is None or notetype_id is None:
            raise AnkiError("could not determine deck/notetype; pass --deck and --notetype")

        if notetype_id == info["current_notetype_id"] and info["current_fields"]:
            field_names = info["current_fields"]
        else:
            field_names = self.get_notetype_fields(notetype_id)
        if not field_names:
            raise AnkiError(f"notetype {notetype_id} has no fields")

        field_vals = [""] * len(field_names)
        if len(values) > len(field_names):
            raise AnkiError(
                f"notetype has {len(field_names)} fields {field_names}, "
                f"but {len(values)} positional values were given"
            )
        for idx, v in enumerate(values):
            field_vals[idx] = v
        for k, v in (named or {}).items():
            if k not in field_names:
                raise AnkiError(f"unknown field '{k}'; available: {field_names}")
            field_vals[field_names.index(k)] = v
        if not any(field_vals):
            raise AnkiError("refusing to add an empty note (no field values given)")

        body = b"".join(pb_string(1, fv) for fv in field_vals)
        if tags:
            body += pb_string(2, tags)
        body += pb_message(3, pb_int(1, notetype_id) + pb_int(2, deck_id))  # add mode
        self._svc(ANKIUSER, "/svc/editor/add-or-update", body)
        return {"deck_id": deck_id, "notetype_id": notetype_id,
                "fields": dict(zip(field_names, field_vals)), "tags": tags}

    def search(self, query: str) -> list[tuple[int, str]]:
        """Find notes matching an Anki search query -> [(note_id, summary), ...].

        `query` uses Anki's search syntax (e.g. 'deck:Spanish', 'front:hola',
        'tag:verb', or just free text). Runs on ankiweb.net (cookie c=1).
        """
        self.ensure_login()
        raw = self._svc(ANKIWEB, "/svc/search/search", pb_string(1, query))
        out = []
        for m in pb_decode(raw).get(1, []):
            d = pb_decode(m)
            out.append((d.get(1, [0])[0], _as_str(d.get(2, [b""])[0])))
        return out

    def get_note_info(self, note_id: int) -> dict:
        """Current field names/values and tags for a note (ankiuser.net)."""
        self.ensure_login()
        d = pb_decode(self._svc(ANKIUSER, "/svc/editor/get-note-info", pb_int(1, int(note_id))))
        names = self._field_names(d.get(2, []))
        if not names:
            raise AnkiError(f"note {note_id} not found (no fields returned)")
        return {
            "fields": names,                                  # field names, in order
            "values": [_as_str(v) for v in d.get(1, [])],     # current field values
            "tags": _as_str(d.get(3, [b""])[0]),              # space-separated tags
        }

    def update_card(self, note_id, values=(), named=None, tags=None) -> dict:
        """Edit an existing note in place. Unspecified fields keep their current
        value; tags are preserved unless `tags` is given. Uses the same
        add-or-update endpoint as add_card but in *edit mode* (field 4 = note id),
        so it never creates a duplicate note."""
        info = self.get_note_info(note_id)
        field_names = info["fields"]
        field_vals = list(info["values"]) + [""] * (len(field_names) - len(info["values"]))
        if len(values) > len(field_names):
            raise AnkiError(
                f"note has {len(field_names)} fields {field_names}, "
                f"but {len(values)} positional values were given"
            )
        for idx, v in enumerate(values):
            field_vals[idx] = v
        for k, v in (named or {}).items():
            if k not in field_names:
                raise AnkiError(f"unknown field '{k}'; available: {field_names}")
            field_vals[field_names.index(k)] = v
        out_tags = info["tags"] if tags is None else tags

        body = b"".join(pb_string(1, fv) for fv in field_vals)
        if out_tags:
            body += pb_string(2, out_tags)
        body += pb_message(4, pb_int(1, int(note_id)))  # edit mode
        self._svc(ANKIUSER, "/svc/editor/add-or-update", body)
        return {"note_id": int(note_id),
                "fields": dict(zip(field_names, field_vals)), "tags": out_tags}

    # ---- decks (ankiweb.net) ------------------------------------------------
    def create_deck(self, name: str) -> int | None:
        self.ensure_login()
        self._svc(ANKIWEB, "/svc/decks/create-deck", pb_string(1, name))
        # response is empty; resolve the new id from the (flat) deck list
        for did, dname in self.get_info_for_adding()["decks"]:
            if dname == name:
                return did
        return None

    def remove_deck(self, deck) -> int:
        self.ensure_login()
        deck_id = self._resolve(deck, self.get_info_for_adding()["decks"], "deck")
        self._svc(ANKIWEB, "/svc/decks/remove-deck", pb_int(1, deck_id))
        return deck_id

    def rename_deck(self, deck, new_name: str) -> dict:
        """Rename a deck (ankiweb.net). A '::' in new_name moves it under a
        parent. The endpoint returns {1: error}; a non-empty error is raised."""
        self.ensure_login()
        deck_id = self._resolve(deck, self.get_info_for_adding()["decks"], "deck")
        raw = self._svc(ANKIWEB, "/svc/decks/rename-deck",
                        pb_int(1, deck_id) + pb_string(2, new_name))
        err = _as_str(pb_decode(raw).get(1, [b""])[0]) if raw else ""
        if err:
            raise AnkiError(f"rename failed: {err}")
        return {"deck_id": deck_id, "new_name": new_name}

    @staticmethod
    def _resolve(value, pairs: list[tuple[int, str]], kind: str) -> int:
        for _id, name in pairs:
            if name == value:
                return _id
        if str(value).isdigit():  # numeric id: accept only if it actually exists
            vid = int(value)
            if any(_id == vid for _id, _ in pairs):
                return vid
            raise AnkiError(f"{kind} id {vid} does not exist")
        matches = [name for _id, name in pairs if str(value).lower() in name.lower()][:5]
        hint = f" Did you mean: {matches}?" if matches else ""
        raise AnkiError(f"{kind} '{value}' not found.{hint}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="anki", description="Minimal AnkiWeb CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("create_deck", help="Create a deck (use '::' to nest)")
    pc.add_argument("name")

    pa = sub.add_parser("add_card", help="Add a note to a deck")
    pa.add_argument("values", nargs="*", help="Field values in notetype order (e.g. Front Back)")
    pa.add_argument("-d", "--deck", help="Deck name or id (default: last used)")
    pa.add_argument("-n", "--notetype", help="Notetype name or id (default: last used)")
    pa.add_argument("-f", "--field", action="append", default=[], metavar="NAME=VALUE",
                    help="Set a field by name (repeatable; overrides positional)")
    pa.add_argument("-t", "--tags", default="", help="Space-separated tags")

    pu = sub.add_parser("update_card", help="Edit an existing note in place (no duplicate)")
    pu.add_argument("note_id", help="Note id (from `search`, or the /edit/<id> URL)")
    pu.add_argument("values", nargs="*",
                    help="New field values in notetype order; omitted trailing "
                         "positions keep their current value")
    pu.add_argument("-f", "--field", action="append", default=[], metavar="NAME=VALUE",
                    help="Set one field by name (repeatable; best for editing a single field)")
    pu.add_argument("-t", "--tags", default=None,
                    help="Replace tags (default: keep the note's existing tags)")

    ps = sub.add_parser("search", help="Find notes; prints 'note_id<TAB>summary'")
    ps.add_argument("query", help="Anki search query, e.g. 'deck:Spanish front:hola'")

    pr = sub.add_parser("remove-deck", help="Remove a deck (and its cards)")
    pr.add_argument("deck", help="Deck name or id")

    prn = sub.add_parser("rename-deck", help="Rename a deck ('::' moves it under a parent)")
    prn.add_argument("deck", help="Current deck name or id")
    prn.add_argument("new_name", help="New deck name")

    sub.add_parser("login", help="Force re-login and refresh the cached session")
    sub.add_parser("list-decks", help="List decks as 'id<TAB>name'")
    sub.add_parser("list-notetypes", help="List notetypes as 'id<TAB>name'")
    return p


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    client = AnkiWebClient()
    try:
        if args.cmd == "login":
            client.login()
            print(f"logged in; session cached to {SESSION_FILE}")
        elif args.cmd == "create_deck":
            did = client.create_deck(args.name)
            print(f"created deck '{args.name}'" + (f" (id {did})" if did else " (id not resolved)"))
        elif args.cmd == "remove-deck":
            did = client.remove_deck(args.deck)
            print(f"removed deck {did}")
        elif args.cmd == "rename-deck":
            res = client.rename_deck(args.deck, args.new_name)
            print(f"renamed deck {res['deck_id']} -> '{res['new_name']}'")
        elif args.cmd == "add_card":
            named = {}
            for f in args.field:
                if "=" not in f:
                    raise AnkiError(f"--field expects NAME=VALUE, got {f!r}")
                k, v = f.split("=", 1)
                named[k] = v
            res = client.add_card(args.deck, args.notetype, args.values, named, args.tags)
            print(f"added card -> deck {res['deck_id']}, notetype {res['notetype_id']}"
                  + (f", tags '{res['tags']}'" if res["tags"] else ""))
            for k, v in res["fields"].items():
                print(f"  {k}: {v!r}")
        elif args.cmd == "update_card":
            if not str(args.note_id).isdigit():
                raise AnkiError(f"note_id must be numeric, got {args.note_id!r}")
            named = {}
            for f in args.field:
                if "=" not in f:
                    raise AnkiError(f"--field expects NAME=VALUE, got {f!r}")
                k, v = f.split("=", 1)
                named[k] = v
            res = client.update_card(args.note_id, args.values, named, args.tags)
            print(f"updated note {res['note_id']}"
                  + (f", tags '{res['tags']}'" if res["tags"] else ""))
            for k, v in res["fields"].items():
                print(f"  {k}: {v!r}")
        elif args.cmd == "search":
            rows = client.search(args.query)
            for nid, summary in rows:
                print(f"{nid}\t{summary}")
            if not rows:
                print("(no matches)", file=sys.stderr)
        elif args.cmd == "list-decks":
            for did, name in client.get_info_for_adding()["decks"]:
                print(f"{did}\t{name}")
        elif args.cmd == "list-notetypes":
            for nid, name in client.get_info_for_adding()["notetypes"]:
                print(f"{nid}\t{name}")
    except AnkiError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
