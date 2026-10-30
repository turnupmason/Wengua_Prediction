"""Bulk editorial grouping regression. Synthetic evidence, no scoring engine change."""
import contextlib
import io
import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from plan_1080_bulk_editorial import main, ensure_source_record, SCORES

DUMMY = "a" * 64
BOARDS = ("yang-08-乙丑", "yin-06-癸亥")


def sample(idx, board=BOARDS[0], branch="甲", month="丙寅", grade="大吉"):
    four = {"year": "甲子", "month": month, "day": "甲子",
            "hour": board.split("-")[-1]}
    result = {
        "status": "原始断词_待润色和人工审核",
        "grade": grade, "score_internal": SCORES[grade],
        "physical_board_id": board,
        "physical_board_json": "physical_1080/" + board + ".json",
        "original_text": "旧原始算法文字只作溯源，不可直接作为新文学稿",
        "original_text_sha256": DUMMY,
        "source_evidence_sha256": DUMMY,
        "sections": [],
        "frozen_fact_lock": {
            "original_physical_board_id": board,
            "selected_roles": {"patient": {"palace": idx % 9 + 1,
                                           "symbol": "甲",
                                           "strength": "source_known"}},
            "person_binding": {"palace": idx % 9 + 1}
        },
    }
    return {
        "schema": "wengua_v80_v102_bigfish_editorial_precompute_v1",
        "branch": branch, "case_id": "source-" + str(idx),
        "immutable_identity": {
            "relationship": "father", "index": idx,
            "four_pillars": four, "term": "立春"
        },
        "original_result": result,
    }


class BulkPlannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = pathlib.Path(self.tmp.name)
        self.inputs = self.root / "input"
        self.boards = self.root / "physical_1080"
        self.output = self.root / "out"
        self.inputs.mkdir()
        self.boards.mkdir()
        for name in BOARDS:
            (self.boards / (name + ".json")).write_text(
                json.dumps({
                    "physical_id": name,
                    "hour_ganzhi": name.split("-")[-1],
                    "dun": name.split("-")[0],
                    "palaces": {str(x): {"palace": x} for x in range(1, 10)},
                    "source_original_raw": {"chart": {"test": True}},
                }, ensure_ascii=False), encoding="utf-8")
        self.infile = self.inputs / "father_000001-005000_待审事实包.jsonl"

    def write(self, rows):
        self.infile.write_text(
            "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in rows),
            encoding="utf-8"
        )

    def run_planner(self, batch_size=2):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main([
                "--input", str(self.inputs), "--boards-root", str(self.boards),
                "--out", str(self.output), "--branch", "甲",
                "--batch-size", str(batch_size),
            ])

    def test_separate_physical_boards_and_each_independent_record(self):
        self.write([sample(1), sample(2), sample(3),
                    sample(4, board=BOARDS[1], grade="极小凶"),
                    sample(5, branch="乙")])
        self.assertEqual(self.run_planner(), 0)
        manifest = json.loads((self.output / "batch_manifest.json").read_text("utf-8"))
        self.assertEqual(manifest["queued_independent_cases"], 4)
        self.assertEqual(manifest["distinct_physical_board_groups"], 2)
        self.assertEqual(manifest["batches"], 3)  # 3 same-board cases split 2+1
        self.assertEqual(manifest["board_counts"][BOARDS[0]], 3)
        self.assertEqual(manifest["board_counts"][BOARDS[1]], 1)
        self.assertEqual(manifest["app_approved_count"], 0)
        self.assertFalse(manifest["literary_text_generated"])
        cases = []
        for entry in manifest["batch_index"]:
            content = (self.output / entry["path"]).read_text("utf-8")
            self.assertEqual(len(content.splitlines()), entry["rows"])
            for line in content.splitlines():
                case = json.loads(line)
                self.assertNotIn("旧原始算法文字", line)
                self.assertEqual(case["original_grade"], "极小凶" if case["immutable_identity"]["index"] == 4 else "大吉")
                self.assertTrue(case["board_source"]["sha256"])
                self.assertEqual(case["release_status"], "draft_not_approved")
                cases.append(case["immutable_identity"]["index"])
        self.assertEqual(sorted(cases), [1, 2, 3, 4])
        # Safe resume with same facts produces byte-identical immutable batches.
        self.assertEqual(self.run_planner(), 0)

    def test_reject_inconsistent_frozen_score(self):
        obj = sample(1)
        obj["original_result"]["score_internal"] = -5
        with self.assertRaisesRegex(ValueError, "frozen grade"):
            ensure_source_record(obj, "甲")

    def test_fails_closed_without_actual_bigfish_chart(self):
        (self.boards / (BOARDS[0] + ".json")).unlink()
        self.write([sample(1)])
        self.assertEqual(self.run_planner(), 2)
        self.assertFalse((self.output / "batch_manifest.json").exists())
        missing = json.loads((self.output / "missing_original_boards.json").read_text("utf-8"))
        self.assertEqual(missing, [BOARDS[0]])

    def test_quarantines_bad_original_source_and_keeps_valid(self):
        broken = sample(2)
        broken["original_result"]["source_evidence_sha256"] = ""
        self.write([sample(1), broken])
        self.assertEqual(self.run_planner(), 0)
        manifest = json.loads((self.output / "batch_manifest.json").read_text("utf-8"))
        self.assertEqual(manifest["queued_independent_cases"], 1)
        self.assertEqual(manifest["retained_failure_records"], 1)
        with sqlite3.connect(self.output / "editorial_queue.sqlite") as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM failures").fetchone()[0], 1)

if __name__ == "__main__":
    unittest.main()
