import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FOLDER = ROOT / "疾病" / "病情程度" / "盘面" / "阳遁" / "08局"
# Source-locked against actual user-uploaded Father.zip and 1080(1).zip.
SAMPLES = {
    21: ("甲申","乙丑","极大吉",5,8,"b2eae3f99bc42cc98279a90db8f026d1d915a53608c84c20e876af71ef260802","7e4c8aaf4a3feb1f1cad022485e3b13b781b3690fb502195dcc40e3b0995dcf6"),
    22: ("乙酉","乙丑","极大凶",-5,6,"7e0b2c84e13b3a3a6ce004d4b8289adfbe7f8377fb5a7ad8bcd07f6cbbca03c4","12e65725f509246f2d03a0136b105bc05ef63301e45bb8d38c1c5a07f4629ca1"),
    23: ("丙戌","乙丑","大凶",-4,1,"28dac63304983c5238527660699fa075058859dd084068e6b4bbcc88d22559a6","9bc3f1292b6699216efbe21aa515cb9d9c1f59a0c94b519d0a8631e165e8633a"),
    24: ("丁亥","乙丑","大吉",4,7,"f5a232a3a4a440f4035ac7d492d907d2436b695d288814ae7ac7e816008658d8","7837ae3fecd771e04bc9404764427a49326b84ff8d6f44362c383e2ff5349e7c"),
    25: ("戊子","丙寅","极大凶",-5,3,"85b65d4588f3ca54d4e4441668bda6ac57b8713900c7529cc9dffc2928b688f1","858f4825964db8243a94e0cbd877d1afa079976ff1a72492f3d9535510c343cb"),
    26: ("己丑","丙寅","极大凶",-5,2,"73b56927de4add2e79e8e374846e4b157c95c140be99f2e415cc39053f584f42","58454223b2954f29aba32a4e0d8b3ec41dc051c4f61c8dce07c0990aaf487719"),
    27: ("庚寅","丙寅","中凶",-3,8,"b81455653dd809a5af518cd68b40bc5ac20b3ef14edea170e0d97e609ea9cf26","e9c09ce8e7caf2ea0002733a49b3369451e2bf2ebb13a75701992b9c1b01a1f3"),
    28: ("辛卯","丙寅","中凶",-3,7,"08b68a0065f93f67ec3cef4dc7139e0cb654720fe551789fc911834f7dcf937b","6292d326571cf7be4b4504ca6f3b33ed3815dc52d24e09d4b65556e5ea005e59"),
    29: ("壬辰","丙寅","极大凶",-5,4,"4fef11431f2aab3d25aa24362bd8bb3fefecf561b168d35329ed21892064f686","d0c5ce061933040d94ed86c5759e8248c479a5f67d0747b13f8d8c24fe47319e"),
    30: ("癸巳","丙寅","极大凶",-5,9,"273c70622f8926998cd9c7d449cec377fa745f681979c6bbc43cc46a2cb48e2c","1381a72231710d2a1b466b933bd2fd30b7c453522df68c4b45053a31f14443b9"),
}
SECTIONS = {"macro","illness","patient","doctor","medicine","hour","chief","gender","verdict","timing"}
BANNED = ("计分","评分","宫分","加分","重复计算","冻结","score","源力量","源强")
FRONT_BANNED = ("天芮","天心","乙奇","丁奇","值符","白虎","伏吟","反吟","坤二","乾六","生门","死门")


class UploadedSourceWritingTests(unittest.TestCase):
    def test_new_upload_batch_evidence_and_literature_quality(self):
        for number,(hour,day,grade,score,palace,evidence,board_sha) in SAMPLES.items():
            path=FOLDER / hour / "父亲" / ("case-%06d-jieqi-a.v9.json" % number)
            with self.subTest(number=number):
                record=json.loads(path.read_text(encoding="utf-8"))
                src,lock,ed=record["source_context"],record["fact_lock"],record["editorial"]
                self.assertEqual(src["scenario_id"],number)
                self.assertEqual((src["year"],src["month"],src["day"],src["hour"]),("甲子","丙寅",day,hour))
                self.assertEqual(src["solar_term_branch"],"a")
                self.assertEqual(record["physical_chart"]["key"],"yang-08-"+hour)
                self.assertEqual(lock["original_evidence_sha256"],evidence)
                self.assertRegex(lock["original_text_sha256"],"^[0-9a-f]{64}$")
                self.assertEqual(lock["physical_board_sha256"],board_sha)
                self.assertEqual(lock["grade"],grade)
                self.assertEqual(lock["score"],score)
                self.assertEqual(lock["patient_palace"],palace)
                self.assertEqual((lock["patient_symbol"],lock["patient_source_ganzhi"],lock["carrier_stem"]),("甲","甲子","戊"))
                self.assertEqual(ed["version"],9)
                self.assertEqual((ed["status"],ed["human_approved"]),("draft",False))
                self.assertEqual(set(ed["professional_sections"]),SECTIONS)
                self.assertEqual(set(ed["professional_section_titles"]),SECTIONS)
                self.assertTrue(all(len(v.strip())>=35 for v in ed["professional_sections"].values()))
                front=ed["front_screen"]["text"]
                self.assertTrue(360<=len(front)<=1100)
                self.assertNotIn("？",front)
                self.assertEqual(ed["front_screen"]["title"].split("：")[0],grade)
                self.assertIn("父亲",front)
                self.assertIn("病情",front)
                self.assertIn("医生",front)
                self.assertIn("药物",front)
                self.assertFalse(any(t in front for t in FRONT_BANNED))
                visible=front+"\n"+"\n".join(ed["professional_sections"].values())
                self.assertFalse(any(t in visible for t in BANNED))

    def test_case_29_five_not_meet_and_antiphon_are_explicit(self):
        r=json.loads((FOLDER/"壬辰"/"父亲"/"case-000029-jieqi-a.v9.json").read_text(encoding="utf-8"))
        self.assertIn("五不遇",r["editorial"]["professional_sections"]["macro"])
        self.assertIn("反吟",r["editorial"]["professional_sections"]["macro"])
        self.assertEqual(r["fact_lock"]["grade"],"极大凶")

if __name__ == "__main__":
    unittest.main()
