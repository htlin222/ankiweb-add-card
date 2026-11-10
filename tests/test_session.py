"""A malformed cached session must never crash the CLI on startup."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skill" / "anki"))

import anki


def _client_with_session(monkeypatch, tmp_path, payload):
    session_file = tmp_path / "anki_session.json"
    session_file.write_text(payload, encoding="utf-8")
    monkeypatch.setattr(anki, "SESSION_FILE", session_file)
    return anki.AnkiWebClient()


def test_session_entry_missing_keys_is_skipped(monkeypatch, tmp_path):
    client = _client_with_session(
        monkeypatch, tmp_path, json.dumps({"cookies": [{"name": "ankiweb", "value": "x"}]})
    )
    assert list(client.client.cookies.jar) == []


def test_non_dict_session_entries_are_skipped(monkeypatch, tmp_path):
    payload = json.dumps({"cookies": ["stale", 42, None, {"name": "n", "value": "v", "domain": "d"}]})
    client = _client_with_session(monkeypatch, tmp_path, payload)
    assert [c.name for c in client.client.cookies.jar] == ["n"]


def test_non_dict_session_doc_is_ignored(monkeypatch, tmp_path):
    client = _client_with_session(monkeypatch, tmp_path, json.dumps([1, 2, 3]))
    assert list(client.client.cookies.jar) == []


def test_valid_session_still_loads(monkeypatch, tmp_path):
    payload = json.dumps(
        {"cookies": [{"name": "ankiweb", "value": "abc", "domain": "ankiweb.net"}]}
    )
    client = _client_with_session(monkeypatch, tmp_path, payload)
    assert [(c.name, c.value) for c in client.client.cookies.jar] == [("ankiweb", "abc")]
