#!/usr/bin/env python3
"""Build 血專口試快答-style Front/Back HTML from JSON, optionally adding the cards.

    python3 make_fields.py card.json                 # print Front / Back HTML
    python3 make_fields.py card.json --add -d DECK   # add via ../../anki.py
    python3 make_fields.py card.json --preview preview.html   # light + dark preview page

card.json is one card object or a list of them:

    {
      "qid": "110-001・Q1",
      "topic": "von Willebrand disease 的診斷路徑與切點",
      "ask": "門診來了一個 25 歲女生……你從哪一步開始？",
      "keywords": ["pretest probability", "ISTH-BAT", "VWF:Ag"],
      "answer": "第一步先判斷 pretest probability……",     # str, or list -> <ul>
      "followup": "如果她的一等親已經確診 VWD……（答：……）",
      "note": "主考官想確認的是：……",
      "details": [{"summary": "素材註記", "body": "……"}],  # always folded
      "tags": "110 110-001 凝血 口試快答"
    }

Values are inserted as HTML (so <b>, <i>, <span class="flag"> work); escape
`<`/`&` yourself if you mean them literally. 關鍵字 and 理想答案 always stay
visible; 追問 and 主考官想確認 fold into <details> once the back is longer
than FOLD_AT characters of text.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

NOTETYPE = "血專口試快答 (Basic)"
FOLD_AT = 500  # visible-text length of the back above which secondary parts fold
ANKI = Path(__file__).resolve().parents[2] / "anki.py"


def _text_len(html: str) -> int:
    return len(re.sub(r"<[^>]+>", "", html))


def _block(value) -> str:
    if isinstance(value, list):
        return "<ul>" + "".join(f"<li>{v}</li>" for v in value) + "</ul>"
    return f"<p>{value}</p>"


def _section(cls: str, label: str, body: str, fold: bool) -> str:
    if fold:
        return f'<details class="{cls}"><summary>{label}</summary><div class="body">{body}</div></details>'
    if cls == "note":
        return f'<div class="note">{body}</div>'
    return f'<div class="{cls}"><b>{label}</b>{body}</div>'


def build(card: dict) -> tuple[str, str]:
    front = (
        f'<div class="qid">{card["qid"]}</div>'
        f'<div class="topic">{card["topic"]}</div>'
        f'<div class="ask">{card["ask"]}</div>'
    )

    kw = card.get("keywords")
    if isinstance(kw, list):
        kw = " · ".join(kw)
    head = f'<div class="kw"><b>關鍵字</b><br>{kw}</div>' if kw else ""
    head += _section("ans", "理想答案", _block(card["answer"]), fold=False)

    secondary = []
    if card.get("followup"):
        secondary.append(("fu", "追問", _block(card["followup"])))
    if card.get("note"):
        secondary.append(("note", "主考官想確認", card["note"]))

    extras = "".join(
        _section("more", d["summary"], d["body"], fold=True) for d in card.get("details", [])
    )
    total = _text_len(head) + sum(_text_len(b) for *_, b in secondary)
    fold = total > FOLD_AT
    back = head + "".join(_section(c, l, b, fold) for c, l, b in secondary) + extras
    return front, back


PREVIEW = """<!doctype html>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>血專口試快答 preview</title>
<link rel="stylesheet" href="style.css">
<style>
  body {{ margin: 0; background: #888; font: 13px sans-serif; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; padding: 16px; }}
  .grid h2 {{ grid-column: 1 / -1; margin: 8px 0 0; color: #fff; font-size: 14px; }}
  .label {{ color: #fff; margin-bottom: 4px; }}
</style>
<div class="grid">{cards}</div>
"""


def preview(cards: list[dict]) -> str:
    out = []
    for card in cards:
        front, back = build(card)
        side = f'{front}<hr id="answer">{back}'
        out.append(f"<h2>{card['qid']}</h2>")
        for label, cls in (("follows system theme (AnkiWeb)", "card"),
                           (".nightMode (desktop / mobile night mode)", "card nightMode")):
            out.append(f'<div><div class="label">{label}</div><div class="{cls}">{side}</div></div>')
    return PREVIEW.format(cards="\n".join(out))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("json", type=Path)
    p.add_argument("--add", action="store_true", help="add the card(s) to AnkiWeb")
    p.add_argument("-d", "--deck", help="deck name or id (with --add)")
    p.add_argument("--preview", type=Path, metavar="HTML", help="write a preview page")
    args = p.parse_args()

    data = json.loads(args.json.read_text())
    cards = data if isinstance(data, list) else [data]
    if args.preview:
        args.preview.write_text(preview(cards))
        print(f"wrote {args.preview}")
        return
    for card in cards:
        front, back = build(card)
        if not args.add:
            print(f"--- Front\n{front}\n--- Back\n{back}\n")
            continue
        cmd = [sys.executable, str(ANKI), "add_card", "-n", NOTETYPE, front, back]
        if args.deck:
            cmd += ["-d", args.deck]
        if card.get("tags"):
            cmd += ["-t", card["tags"]]
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
