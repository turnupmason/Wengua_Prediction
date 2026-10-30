import json,pathlib,sqlite3,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from build_offline_catalog import build,validate
from plan_board_groups import build_index,plan_path
BOARD=ROOT/"疾病/病情程度/盘面"
CASE=BOARD/"阳遁/08局/甲子/父亲/case-000001-jieqi-a.v9.json"
class ReadingContractTests(unittest.TestCase):
 def test_old_readings_removed_and_frozen_evidence(self):
  self.assertEqual(sorted(BOARD.rglob("case-*.json")),[CASE])
  d=json.loads(CASE.read_text(encoding="utf-8"))
  self.assertFalse(validate(d,CASE,ROOT))
  self.assertEqual(d["source_context"]["natal_mode"],"none")
  self.assertEqual(d["source_context"]["solar_term_branch"],"a")
  self.assertEqual(d["fact_lock"]["grade"],"极大吉")
  self.assertEqual(d["fact_lock"]["score"],5)
  self.assertEqual(d["fact_lock"]["patient_palace"],8)
  self.assertEqual(d["fact_lock"]["original_evidence_sha256"],"16ddb33de2fd9339b9b54bbef57b89216c9629495bebc8f9dfa338f6db43acfb")
  self.assertEqual(d["fact_lock"]["original_text_sha256"],"657ef2faf4bd22de827d4ce17ae58fae767fa16024165ddc746c7394391851d1")
  self.assertFalse(d["editorial"]["human_approved"])
 def test_no_draft_in_ios(self):
  with tempfile.TemporaryDirectory() as d:
   out=pathlib.Path(d)/"readings.sqlite"
   manifest=build(ROOT,out)
   self.assertEqual(manifest["approved_count"],0)
   with sqlite3.connect(out) as db:
    self.assertEqual(db.execute("SELECT COUNT(*) FROM readings").fetchone()[0],0)
    self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0],"ok")
 def test_requires_signature(self):
  d=json.loads(CASE.read_text(encoding="utf-8"))
  d["editorial"]["status"]="approved";d["editorial"]["human_approved"]=False
  with self.assertRaises(AssertionError):validate(d,CASE,ROOT)
 def test_board_paths_keep_independent_cases(self):
  a=plan_path("yang-08-甲子","father",1,"a")
  b=plan_path("yang-08-甲子","father",181,"a")
  self.assertNotEqual(a,b)
  self.assertIn("case-000181",b)
if __name__=="__main__":unittest.main()
