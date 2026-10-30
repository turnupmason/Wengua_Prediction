"""Regression: novice-oriented Chinese prose, immutable case facts, six roles."""
import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from render_reading_zh import SECTION_LABELS, SECTION_ORDER, render_chinese_reading

BOARD = ROOT / "疾病" / "病情程度" / "盘面" / "阳遁" / "08局" / "甲子" / "父亲"


def read(name):
    return json.loads((BOARD / name).read_text(encoding="utf-8"))


class ChineseReaderEditorialV8Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old = read("case-000001-jieqi-a.v7.json")
        cls.new = read("case-000001-jieqi-a.v8.json")

    def test_immutable_source_facts_and_frozen_grade(self):
        for key in ("physical_chart", "source_context", "fact_lock", "source_provenance"):
            self.assertEqual(self.old[key], self.new[key], key)
        self.assertEqual(self.new["fact_lock"]["grade"], "极大吉")
        self.assertEqual(self.new["fact_lock"]["score"], 5)
        self.assertEqual(self.new["record_id"], "father-000001-jieqi-a-v8")
        self.assertEqual(self.new["editorial"]["version"], 8)
        self.assertEqual(self.new["editorial"]["status"], "draft")
        self.assertFalse(self.new["editorial"]["human_approved"])

    def test_beginner_front_screen_no_unexplained_technical_tokens(self):
        front = self.new["editorial"]["front_screen"]
        self.assertEqual(front["banner"], "吉局")
        self.assertEqual(front["title"], "极大吉：沉疴顿愈")
        for bad in ("生门", "死门", "值符", "丁奇", "天心", "乙奇", "坤二",
                    "macro", "illness", "doctor", "medicine", "取吉", "？", "?"):
            self.assertNotIn(bad, front["text"])
        self.assertTrue(250 <= len(front["text"]) <= 900)
        for meaning in ("父亲", "疾病", "医生", "药物", "病情变化", "男性长辈",
                        "整体", "较慢"):
            self.assertIn(meaning, front["text"])

    def test_all_six_roles_are_explained_with_actual_shared_palaces(self):
        sections = self.new["editorial"]["professional_sections"]
        self.assertEqual(set(sections), set(SECTION_ORDER))
        self.assertIn("坤二", sections["illness"])
        self.assertIn("艮八", sections["patient"])
        self.assertIn("乾六", sections["doctor"])
        self.assertIn("兑七", sections["medicine"])
        self.assertIn("艮八", sections["hour"])
        self.assertIn("艮八", sections["chief"])
        self.assertIn("乾六", sections["gender"])
        self.assertIn("真空", sections["doctor"])
        self.assertIn("入墓", sections["doctor"])
        self.assertIn("伏吟", sections["timing"])
        self.assertIn("直接克制", sections["medicine"])
        self.assertIn("不能把", sections["gender"])

    def test_reader_display_has_chinese_section_headings(self):
        self.assertEqual(self.new["editorial"]["professional_section_titles"], SECTION_LABELS)
        output = render_chinese_reading(self.new)
        for key in SECTION_ORDER:
            self.assertIn("## " + SECTION_LABELS[key], output)
            self.assertNotIn("## " + key, output)
        self.assertEqual(output.count("\n## "), 10)
        with self.assertRaises(PermissionError):
            render_chinese_reading(self.new, draft_preview=False)

    def test_no_extra_board_score_conclusions(self):
        text = render_chinese_reading(self.new)
        self.assertNotIn("已经痊愈", text)
        self.assertNotIn("一定治愈", text)
        self.assertNotIn("几月几日痊愈", text)


if __name__ == "__main__":
    unittest.main()
