"""Offline tests for skill/anki/anki.py — no AnkiWeb account or network needed.

Run with `make test` (or `python3 -m unittest discover -s tests`).
"""
import base64
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skill" / "anki"))

import anki  # noqa: E402


def offline_client() -> anki.AnkiWebClient:
    """A client whose network calls are stubbed; `sent` records (path, body)."""
    c = object.__new__(anki.AnkiWebClient)
    c.sent = []
    c.ensure_login = lambda *a, **k: None
    c._svc = lambda base, path, body=b"", **k: c.sent.append((path, body)) or b""
    return c


class Protobuf(unittest.TestCase):
    def test_varint_roundtrip(self):
        for n in (0, 1, 127, 128, 300, 2**32, 1792485909266):
            v, i = anki._read_varint(anki._varint(n), 0)
            self.assertEqual((v, i), (n, len(anki._varint(n))))

    def test_message_roundtrip(self):
        raw = anki.pb_string(1, "標籤") + anki.pb_string(1, "b") + anki.pb_int(2, 42) \
            + anki.pb_message(3, anki.pb_int(1, 7))
        d = anki.pb_decode(raw)
        self.assertEqual([anki._as_str(v) for v in d[1]], ["標籤", "b"])
        self.assertEqual(d[2], [42])
        self.assertEqual(anki.pb_decode(d[3][0]), {1: [7]})


class Resolve(unittest.TestCase):
    PAIRS = [(11, "Spanish"), (12, "Spanish::Verbs")]

    def test_by_name_and_id(self):
        self.assertEqual(anki.AnkiWebClient._resolve("Spanish::Verbs", self.PAIRS, "deck"), 12)
        self.assertEqual(anki.AnkiWebClient._resolve("11", self.PAIRS, "deck"), 11)

    def test_unknown_id_and_suggestion(self):
        with self.assertRaisesRegex(anki.AnkiError, "does not exist"):
            anki.AnkiWebClient._resolve("99", self.PAIRS, "deck")
        with self.assertRaisesRegex(anki.AnkiError, "Did you mean"):
            anki.AnkiWebClient._resolve("verbs", self.PAIRS, "deck")


class AddOrUpdateRequests(unittest.TestCase):
    """The add-or-update body is the protocol contract; check it field by field."""

    def test_add_card_body(self):
        c = offline_client()
        c.get_info_for_adding = lambda: {
            "notetypes": [(5, "Basic")], "decks": [(9, "Spanish")],
            "current_deck_id": 9, "current_notetype_id": 5, "current_fields": ["Front", "Back"],
        }
        c.add_card("Spanish", "Basic", ["hola"], {"Back": "hello"}, "t1 t2",
                   append=[(None, "<i>x</i>")])
        path, body = c.sent[0]
        d = anki.pb_decode(body)
        self.assertEqual(path, "/svc/editor/add-or-update")
        self.assertEqual([anki._as_str(v) for v in d[1]], ["hola<i>x</i>", "hello"])
        self.assertEqual(anki._as_str(d[2][0]), "t1 t2")
        self.assertEqual(anki.pb_decode(d[3][0]), {1: [5], 2: [9]})  # add mode: notetype, deck

    def test_add_card_rejects_empty_and_unknown_field(self):
        c = offline_client()
        c.get_info_for_adding = lambda: {
            "notetypes": [(5, "Basic")], "decks": [(9, "D")],
            "current_deck_id": 9, "current_notetype_id": 5, "current_fields": ["Front", "Back"],
        }
        with self.assertRaisesRegex(anki.AnkiError, "empty note"):
            c.add_card()
        with self.assertRaisesRegex(anki.AnkiError, "unknown field"):
            c.add_card(named={"Nope": "x"})
        self.assertEqual(c.sent, [])

    def test_update_card_preserves_untouched_fields_and_tags(self):
        c = offline_client()
        c.get_note_info = lambda nid: {"fields": ["Front", "Back"], "values": ["q", "a"],
                                       "tags": "keep"}
        c.update_card(123, named={"Back": "a2"}, append=[("Front", "!")])
        d = anki.pb_decode(c.sent[0][1])
        self.assertEqual([anki._as_str(v) for v in d[1]], ["q!", "a2"])
        self.assertEqual(anki._as_str(d[2][0]), "keep")
        self.assertEqual(anki.pb_decode(d[4][0]), {1: [123]})  # edit mode: note id


class AppendAndDisplay(unittest.TestCase):
    def test_append_defaults_to_first_field(self):
        vals = ["a", "b"]
        anki._append_html(["Front", "Back"], vals, [(None, "1"), ("Back", "2")])
        self.assertEqual(vals, ["a1", "b2"])
        with self.assertRaisesRegex(anki.AnkiError, "unknown field"):
            anki._append_html(["Front"], ["a"], [("Back", "x")])

    def test_short_collapses_widgets_and_data_uris(self):
        field = "Q" + anki.type_in_html("APL|M3") + '<audio src="data:audio/mpeg;base64,' + "A" * 4000 + '">'
        self.assertEqual(anki._short(field), 'Q[type-in: APL|M3]<audio src="data:audio/mpeg;base64,…3KB">')


class TypeIn(unittest.TestCase):
    def test_widget_carries_answer_and_assets(self):
        html = anki.type_in_html("  急性 APL|M3 ")
        b64 = html.split('data-ans="', 1)[1].split('"', 1)[0]
        self.assertEqual(base64.b64decode(b64).decode(), "急性 APL|M3")
        self.assertIn(".tyin input", html)                 # CSS inlined
        self.assertIn("function isBack()", html)           # JS inlined
        self.assertNotIn("// Type-in answer widget", html)  # header comment dropped

    def test_empty_answer_rejected(self):
        with self.assertRaises(anki.AnkiError):
            anki.type_in_html("  ")

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_js_is_valid(self):
        subprocess.run(["node", "--check", str(anki.ASSETS / "type-in.js")], check=True)


class Audio(unittest.TestCase):
    def test_google_embeds_mp3(self):
        resp = mock.MagicMock()
        resp.__enter__.return_value = resp
        resp.headers.get.return_value = "audio/mpeg"
        resp.read.return_value = b"ID3fake"
        with mock.patch.object(anki.urllib.request, "urlopen", return_value=resp) as urlopen:
            html = anki.tts_audio_html("tag", "en")
        self.assertIn("tl=en", urlopen.call_args[0][0].full_url)
        self.assertEqual(html, '<audio controls src="data:audio/mpeg;base64,'
                               + base64.b64encode(b"ID3fake").decode() + '"></audio>')

    def test_google_rejects_non_audio_and_long_text(self):
        resp = mock.MagicMock()
        resp.__enter__.return_value = resp
        resp.headers.get.return_value = "text/html"
        resp.read.return_value = b"<html>"
        with mock.patch.object(anki.urllib.request, "urlopen", return_value=resp):
            with self.assertRaisesRegex(anki.AnkiError, "instead of audio"):
                anki.tts_audio_html("tag")
        with self.assertRaisesRegex(anki.AnkiError, "limit"):
            anki.tts_audio_html("x" * (anki.TTS_MAX_CHARS + 1))

    def test_piper_needs_a_voice_for_unmapped_language(self):
        with self.assertRaisesRegex(anki.AnkiError, "--audio-voice"):
            anki.tts_audio_html("hallo", "de", engine="piper")


class Cli(unittest.TestCase):
    def test_parser_flags(self):
        a = anki.build_parser().parse_args(
            ["update_card", "1", "-a", "hi", "-a", "yo", "--audio-engine", "piper",
             "--type-answer", "x|y", "--type-field", "Back"])
        self.assertEqual((a.audio, a.audio_engine, a.type_answer, a.type_field),
                         (["hi", "yo"], "piper", "x|y", "Back"))


if __name__ == "__main__":
    unittest.main()
