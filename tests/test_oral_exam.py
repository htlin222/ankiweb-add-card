"""Tests for the oral-exam card style generator (styles/oral-exam/make_fields.py)."""
import json
import sys
import unittest
from pathlib import Path

STYLE = Path(__file__).resolve().parents[1] / "styles" / "oral-exam"
sys.path.insert(0, str(STYLE))

import make_fields  # noqa: E402

EXAMPLES = json.loads((STYLE / "example.json").read_text())


class Build(unittest.TestCase):
    def test_front_structure(self):
        front, _ = make_fields.build(EXAMPLES[0])
        for cls in ("qid", "topic", "ask"):
            self.assertIn(f'<div class="{cls}">', front)

    def test_short_back_stays_open(self):
        _, back = make_fields.build(EXAMPLES[0])
        self.assertNotIn("<details", back)
        self.assertIn('<div class="kw"><b>關鍵字</b>', back)

    def test_long_back_folds_secondary_parts_only(self):
        _, back = make_fields.build(EXAMPLES[1])
        self.assertIn('<details class="fu"><summary>追問</summary>', back)
        self.assertIn('<details class="note">', back)
        self.assertIn('<div class="ans"><b>理想答案</b>', back)  # the graded part never folds

    def test_extra_details_always_fold_and_lists_render(self):
        _, back = make_fields.build(EXAMPLES[2])
        self.assertIn('<details class="more"><summary>素材註記</summary>', back)
        self.assertIn("<ul><li>", back)

    def test_preview_shows_both_themes(self):
        html = make_fields.preview(EXAMPLES[:1])
        self.assertIn('class="card nightMode"', html)
        self.assertIn('href="style.css"', html)


if __name__ == "__main__":
    unittest.main()
