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


from plan_board_groups import build_index, plan_path

class BoardGroupPlanningTests(unittest.TestCase):
    def test_exact_physical_board_path(self):
        self.assertEqual(
            plan_path("yang-08-甲子","father",181,"a"),
            "疾病/病情程度/盘面/阳遁/08局/甲子/父亲/case-000181-jieqi-a.v1.json")

    def test_csv_stages_without_publishing(self):
        import csv
        with tempfile.TemporaryDirectory() as td:
            folder=pathlib.Path(td)
            csv_path=folder/"demo.csv"
            with csv_path.open("w",encoding="utf-8-sig",newline="") as fp:
                w=csv.DictWriter(fp,fieldnames=["序号","年柱","月柱","日柱","时柱","起局甲","节气甲","原等级甲","原文SHA256","原证据SHA"])
                w.writeheader()
                w.writerow({"序号":"1","年柱":"甲子","月柱":"丙寅","日柱":"甲子","时柱":"甲子",
                            "起局甲":"阳8局上元","节气甲":"立春","原等级甲":"极大吉"})
                w.writerow({"序号":"181","年柱":"甲子","月柱":"丙寅","日柱":"己卯","时柱":"甲子",
                            "起局甲":"阳8局上元","节气甲":"立春","原等级甲":"极大吉"})
            manifest=build_index(csv_path,folder/"out")
            self.assertEqual(manifest["board_keys"],1)
            self.assertEqual(manifest["records"],2)
            self.assertEqual(manifest["all_records_status"],"not_approved")
            self.assertEqual(manifest["group_counts"]["yang-08-甲子"],2)

if __name__=="__main__":
    unittest.main()
