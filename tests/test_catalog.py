import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from build_offline_catalog import build, validate
from plan_board_groups import plan_path

BOARD = ROOT / "疾病" / "病情程度" / "盘面"
GRADE_SCORE = {
    "极大吉":5,"大吉":4,"中吉":3,"小吉":2,"极小吉":1,
    "微恙":0,"极小凶":-1,"小凶":-2,"中凶":-3,"大凶":-4,"极大凶":-5,
}
# Lock original BigFish/score evidence, not a hash of edited text.
SOURCE_LOCK = {
   1:("甲子","极大吉",5,8,"16ddb33de2fd9339b9b54bbef57b89216c9629495bebc8f9dfa338f6db43acfb"),
   2:("乙丑","大吉",4,7,"f54045f5806cc368e1ed0da7aee093a12a029d25c23adf576a598ae0f466298f"),
   3:("丙寅","小吉",2,6,"623d43272234df5af79ed3b523179c6dd065eaf0a1693ea86dbf09a74c81182a"),
   4:("丁卯","极小凶",-1,2,"f33268d3fdb278614e1f0f888afe27ba67c8b1c886bed596893f5977707d30a2"),
   5:("戊辰","中吉",3,8,"17b1fde62b3e7a0205d4f0e4a260ff60c8e28d5daab364d6de90dac13f5c64ea"),
   6:("己巳","大凶",-4,9,"4943f2ab32b036bddae68747abb4366c8aec42d4205093053a245b8ed66ff094"),
   7:("庚午","极大凶",-5,1,"131a6aa1141e3cda71fccb24e31a568d371de81471d3d3e589f7e661789ed01c"),
   8:("辛未","极小凶",-1,2,"9dbb7dc19311ca2ae9c76c5720ae6333434d6bec5d2013aa690eb4a494142d32"),
   9:("壬申","极大凶",-5,3,"a1f2bee4a5d2863f998065e2e6e83e43b2b8faf4e3f26d099fb5da84fa8cf175"),
  10:("癸酉","极大吉",5,4,"5146855e74a55f6e32c33565e9f3acfbba70f3125239fd79675821633cd746b2"),
  11:("甲戌","极大吉",5,8,"b7c97337743ebab79669adc5584d09ec93811140378dc25339ded85bd103f5a7"),
}


class ReadingContractTests(unittest.TestCase):
    def test_current_batched_cases_only_v9_and_source_sha_exact(self):
        paths=sorted(BOARD.rglob("case-*.json"))
        self.assertEqual(len(paths), len(SOURCE_LOCK))
        seen=set()
        for path in paths:
            data=json.loads(path.read_text(encoding="utf-8"))
            self.assertFalse(validate(data,path,ROOT))
            n=data["source_context"]["scenario_id"]
            self.assertIn(n,SOURCE_LOCK)
            self.assertNotIn(n,seen)
            seen.add(n)
            hour,grade,score,palace,sha=SOURCE_LOCK[n]
            self.assertEqual(data["record_id"],"father-%06d-jieqi-a-v9"%n)
            self.assertEqual(path.name,"case-%06d-jieqi-a.v9.json"%n)
            self.assertEqual(data["physical_chart"]["key"],"yang-08-"+hour)
            self.assertEqual(data["source_context"]["year"],"甲子")
            self.assertEqual(data["source_context"]["month"],"丙寅")
            self.assertEqual(data["source_context"]["hour"],hour)
            self.assertEqual(data["source_context"]["solar_term_branch"],"a")
            self.assertEqual(data["source_context"]["natal_mode"],"none")
            self.assertEqual(data["fact_lock"]["grade"],grade)
            self.assertEqual(data["fact_lock"]["score"],score)
            self.assertEqual(data["fact_lock"]["patient_palace"],palace)
            self.assertEqual(data["fact_lock"]["original_evidence_sha256"],sha)
            self.assertEqual(data["fact_lock"]["patient_symbol"],"甲")
            self.assertEqual(data["fact_lock"]["patient_source_ganzhi"],"甲子")
            self.assertEqual(data["fact_lock"]["carrier_stem"],"戊")
            self.assertEqual(data["editorial"]["status"],"draft")
            self.assertFalse(data["editorial"]["human_approved"])
            self.assertEqual(data["editorial"]["version"],9)
            self.assertEqual(data["editorial"]["front_screen"]["title"].split("：")[0],grade)
            self.assertEqual(score,GRADE_SCORE[grade])
        self.assertEqual(seen,set(SOURCE_LOCK))

    def test_no_draft_enters_offline_catalogue(self):
        with tempfile.TemporaryDirectory() as td:
            out=pathlib.Path(td)/"readings.sqlite"
            report=build(ROOT,out)
            self.assertEqual(report["approved_count"],0)
            with sqlite3.connect(out) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM readings").fetchone()[0],0)
                self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0],"ok")
            with self.assertRaises(FileExistsError):
                build(ROOT,out)

    def test_signoff_cannot_be_forged(self):
        file=next(BOARD.rglob("case-000001-jieqi-a.v9.json"))
        d=json.loads(file.read_text(encoding="utf-8"))
        d["editorial"]["status"]="approved"
        d["editorial"]["human_approved"]=False
        with self.assertRaises(AssertionError):validate(d,file,ROOT)

    def test_same_board_does_not_allow_reusing_other_case(self):
        self.assertNotEqual(plan_path("yang-08-甲子","father",1,"a"),
                            plan_path("yang-08-甲子","father",181,"a"))


if __name__=="__main__":
    unittest.main()
