import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_offline_catalog import build, validate

FILES = sorted((ROOT/"疾病"/"病情程度"/"盘面").rglob("case-*.json"))

class ReadingContractTests(unittest.TestCase):
    def test_samples_exist_and_paths_pass(self):
        self.assertGreaterEqual(len(FILES), 5)
        ids = set()
        for path in FILES:
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertFalse(validate(data, path, ROOT))
            self.assertNotIn(data["record_id"], ids)
            ids.add(data["record_id"])
            self.assertEqual(data["editorial"]["status"], "draft")
            self.assertFalse(data["editorial"]["human_approved"])

    def test_same_board_never_collapses_cases(self):
        a = json.loads((ROOT/"疾病/病情程度/盘面/阳遁/08局/甲子/父亲/case-000001-jieqi-a.v1.json").read_text(encoding="utf-8"))
        b = json.loads((ROOT/"疾病/病情程度/盘面/阳遁/08局/甲子/父亲/case-000181-jieqi-a.v1.json").read_text(encoding="utf-8"))
        self.assertEqual(a["physical_chart"]["key"], b["physical_chart"]["key"])
        self.assertNotEqual(a["record_id"], b["record_id"])
        self.assertNotEqual(a["source_context"]["day"], b["source_context"]["day"])
        self.assertNotEqual(a["fact_lock"]["original_evidence_sha256"], b["fact_lock"]["original_evidence_sha256"])
        self.assertNotEqual(a["editorial"]["front_screen"]["text"], b["editorial"]["front_screen"]["text"])

    def test_wei_yang_is_neutral(self):
        p=ROOT/"疾病/病情程度/盘面/阳遁/08局/乙巳/父亲/case-000042-jieqi-a.v1.json"
        r=json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual(r["fact_lock"]["score"], 0)
        self.assertEqual(r["fact_lock"]["grade"], "微恙")
        self.assertIn("不凶不吉", r["editorial"]["front_screen"]["text"])

    def test_no_draft_enter_release(self):
        with tempfile.TemporaryDirectory() as td:
            out=pathlib.Path(td)/"readings.sqlite"
            manifest=build(ROOT,out)
            self.assertEqual(manifest["approved_count"],0)
            db=sqlite3.connect(out)
            try:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM readings").fetchone()[0],0)
                self.assertTrue(db.execute("PRAGMA integrity_check").fetchone()[0] == "ok")
            finally:
                db.close()
            with self.assertRaises(FileExistsError):
                build(ROOT,out)

    def test_approval_requires_signature(self):
        sample=json.loads(FILES[0].read_text(encoding="utf-8"))
        sample["editorial"]["status"]="approved"
        sample["editorial"]["human_approved"]=False
        with self.assertRaises(AssertionError):
            validate(sample,FILES[0],ROOT)

if __name__=="__main__":
    unittest.main()
