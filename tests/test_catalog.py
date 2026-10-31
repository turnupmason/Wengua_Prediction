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

# New v9 GPT literary drafts retain exact source identity, still require human approval.
SOURCE_LOCK.update({'31':['甲午','极大吉',5,8,'dd298e24f6541b4a0d1692d6fb2dee6b58e5e38afdb3ca6ea674e500aee692e7'],'32':['乙未','大吉',4,3,'317021a2912421204eaff26277810769a4e1eee73886fbdca0d587c8c6b35e11'],'33':['丙申','极大吉',5,4,'21a31bd5ae6c31c73e9f2cb3eca0dedfdd6719de71ad89dcdbec34bdf0b5a58a'],'34':['丁酉','极大吉',5,8,'30c5f2d65f1189912e3e299aff10078eb389045a1e3c9aaaf4b63c227f423b64'],'35':['戊戌','极大凶',-5,2,'494c7ff671a7c1ff9afa412f0cab0ddb2ec7bf07d43530f1edf8e2f44cf15cc3'],'36':['己亥','极大凶',-5,1,'a527b83cbb57f3400100c55bbbd845011f97a5d0a32482f98119b3b387b30af7'],'37':['庚子','极大凶',-5,9,'28738ffe12f099cda5eda5365703617e93dd64c5dce2f2a24e4e1149c0f3de35'],'38':['辛丑','极大吉',5,8,'635bfbaf9d343e476dcfff4d32ebcc0990bb9351162fcb732876c290345fbe91'],'39':['壬寅','大吉',4,7,'76379feb593cc2b0a9497a1f849cf1dfeddb02cb415b8282d2a52aee811febe1'],'40':['癸卯','小吉',2,6,'1f2c838d1bbcce05e6510ba2fbf99277b5c90492bc20c695ccab348eebb5def6']})


class ReadingContractTests(unittest.TestCase):
    def test_current_batched_cases_only_v9_and_source_sha_exact(self):
        paths=sorted(BOARD.rglob("case-*.json"))
        self.assertGreaterEqual(len(paths),40)
        self.assertTrue(all(p.name.endswith(".v9.json") for p in paths))
        seen=set()
        for path in paths:
            data=json.loads(path.read_text(encoding="utf-8"))
            n=data["source_context"]["scenario_id"]
            # The validator returns True only for explicitly user-approved texts.
            # New v9 manuscripts are legitimate source-locked drafts, not publishable.
            self.assertEqual(validate(data,path,ROOT), n <= 30)
            self.assertTrue(1<=n<=518400)
            self.assertNotIn(n,seen)
            seen.add(n)
            self.assertEqual(data["record_id"],"father-%06d-jieqi-a-v9"%n)
            self.assertEqual(path.name,"case-%06d-jieqi-a.v9.json"%n)
            self.assertEqual(data["source_context"]["solar_term_branch"],"a")
            self.assertEqual(data["source_context"]["natal_mode"],"none")
            self.assertEqual(data["fact_lock"]["patient_symbol"],"甲")
            self.assertEqual(data["fact_lock"]["patient_source_ganzhi"],"甲子")
            self.assertEqual(data["fact_lock"]["carrier_stem"],"戊")
            if n <= 30:
                self.assertEqual(data["editorial"]["status"], "approved")
                self.assertTrue(data["editorial"]["human_approved"])
                self.assertEqual(data["editorial"]["reviewer"], "user_explicit_approval_2026-10-30")
            else:
                self.assertIn(data["editorial"]["status"], ("draft", "fact_checked", "reviewed"))
                self.assertFalse(data["editorial"]["human_approved"])
                self.assertIsNone(data["editorial"].get("reviewer"))
            self.assertEqual(data["editorial"]["version"],9)
            self.assertEqual(data["editorial"]["front_screen"]["title"].split("：")[0],data["fact_lock"]["grade"])
            self.assertEqual(data["fact_lock"]["score"],GRADE_SCORE[data["fact_lock"]["grade"]])
            self.assertEqual(len(data["fact_lock"]["original_evidence_sha256"]),64)
            self.assertEqual(len(data["fact_lock"]["original_text_sha256"]),64)
            if n in SOURCE_LOCK:
                hour,grade,score,palace,sha=SOURCE_LOCK[n]
                self.assertEqual(data["physical_chart"]["key"],"yang-08-"+hour)
                self.assertEqual(data["source_context"]["year"],"甲子")
                self.assertEqual(data["source_context"]["month"],"丙寅")
                self.assertEqual(data["source_context"]["hour"],hour)
                self.assertEqual(data["fact_lock"]["grade"],grade)
                self.assertEqual(data["fact_lock"]["score"],score)
                self.assertEqual(data["fact_lock"]["patient_palace"],palace)
                self.assertEqual(data["fact_lock"]["original_evidence_sha256"],sha)

        self.assertTrue(set(range(1,41)).issubset(seen))

    def test_only_30_explicitly_approved_readings_enter_offline_catalogue(self):
        with tempfile.TemporaryDirectory() as td:
            out=pathlib.Path(td)/"readings.sqlite"
            report=build(ROOT,out)
            self.assertEqual(report["approved_count"],30)
            with sqlite3.connect(out) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM readings").fetchone()[0],30)
                self.assertEqual({int(r[0].split("-")[1]) for r in db.execute("SELECT record_id FROM readings")},set(range(1,31)))
                self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0],"ok")
            with self.assertRaises(FileExistsError):
                build(ROOT,out)

    def test_signoff_cannot_be_forged(self):
        file=next(BOARD.rglob("case-000001-jieqi-a.v9.json"))
        d=json.loads(file.read_text(encoding="utf-8"))
        d["editorial"]["human_approved"]=False
        with self.assertRaises(AssertionError):validate(d,file,ROOT)

    def test_approved_text_is_byte_locked_and_future_draft_is_not_published(self):
        file=next(BOARD.rglob("case-000001-jieqi-a.v9.json"))
        original=json.loads(file.read_text(encoding="utf-8"))
        tampered=json.loads(json.dumps(original,ensure_ascii=False))
        tampered["editorial"]["front_screen"]["text"] += "新增未经用户审定的一句话"
        with self.assertRaises(AssertionError): validate(tampered,file,ROOT)
        future_draft=json.loads(json.dumps(original,ensure_ascii=False))
        future_draft["editorial"]["status"]="draft"
        future_draft["editorial"]["human_approved"]=False
        future_draft["editorial"]["reviewer"]=None
        self.assertFalse(validate(future_draft,file,ROOT))

    def test_same_board_does_not_allow_reusing_other_case(self):
        self.assertNotEqual(plan_path("yang-08-甲子","father",1,"a"),
                            plan_path("yang-08-甲子","father",181,"a"))


if __name__=="__main__":
    unittest.main()
