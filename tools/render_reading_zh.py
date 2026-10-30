#!/usr/bin/env python3
"""Display-only renderer for Chinese health readings; preserve machine keys internally.

This module is editorial presentation, not casting/scoring. A reader must never
see internal 'macro', 'illness', etc. Do not ship unapproved drafts to iOS.
"""
from __future__ import annotations

import json
import pathlib
import sys

SECTION_LABELS = {
    "macro": "时局与变化节奏",
    "illness": "疾病本身的阻碍",
    "patient": "父亲自身的处境",
    "doctor": "医生与求医条件",
    "medicine": "药物能起多大作用",
    "hour": "当前事情的发展",
    "chief": "父亲得到的扶持",
    "gender": "男性长辈的辅助判断",
    "verdict": "综合判断",
    "timing": "好转时间与条件",
}
SECTION_ORDER = tuple(SECTION_LABELS)


def render_chinese_reading(record: dict, *, draft_preview: bool = True) -> str:
    ed = record["editorial"]
    if not draft_preview and (ed["status"] != "approved" or not ed["human_approved"]):
        raise PermissionError("Unapproved readings must not be published")
    sections = ed["professional_sections"]
    if set(sections) != set(SECTION_ORDER):
        raise ValueError("The reading must contain exactly ten professional sections")
    titles = ed.get("professional_section_titles") or SECTION_LABELS
    if set(titles) != set(SECTION_ORDER):
        raise ValueError("A Chinese title is required for every section")
    if any(not str(titles[k]).strip() or str(titles[k]).isascii() for k in SECTION_ORDER):
        raise ValueError("Professional section headings must be Chinese")
    front = ed["front_screen"]
    result = [front["banner"], front["title"], "", front["text"].strip()]
    for key in SECTION_ORDER:
        result.extend(["", "## " + str(titles[key]), sections[key].strip()])
    return "\n".join(result) + "\n"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: python3 tools/render_reading_zh.py <reading.json> (draft preview only)")
    path = pathlib.Path(sys.argv[1])
    print(render_chinese_reading(json.loads(path.read_text(encoding="utf-8"))), end="")
