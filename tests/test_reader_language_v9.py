import json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from render_reading_zh import SECTION_LABELS,SECTION_ORDER,render_chinese_reading
CASE=ROOT/"疾病/病情程度/盘面/阳遁/08局/甲子/父亲/case-000001-jieqi-a.v9.json"
class UserApprovedStyleTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.r=json.loads(CASE.read_text(encoding="utf-8"))
 def test_confirmed_first_screen_verbatim_boundaries(self):
  front=self.r["editorial"]["front_screen"]
  self.assertEqual(front["banner"],"吉局")
  self.assertEqual(front["title"],"极大吉：沉疴顿愈")
  self.assertEqual(len(front["text"]),467)
  self.assertTrue(front["text"].startswith("父亲这次的病情，虽然有较明显的阻碍，但整体恢复前景仍然有利。"))
  self.assertTrue(front["text"].endswith("只是局势显示变化较慢，好转未必迅速，不宜急着判断何时康复。"))
 def test_role_evidence_and_chinese_titles(self):
  s=self.r["editorial"]["professional_sections"]
  for key,terms in {
   "illness":("天芮","坤二","丁奇","白虎"),
   "patient":("年干甲","艮八","生门","值符"),
   "doctor":("天心","乾六","真空","入墓"),
   "medicine":("乙奇","兑七","玄武"),
   "hour":("时干甲","艮八"),
   "chief":("值符","艮八"),
   "gender":("乾六","辅证"),
   "verdict":("极大吉","病宫"),
   "timing":("伏吟","天显")}.items():
   for t in terms:self.assertIn(t,s[key],key)
  self.assertEqual(self.r["editorial"]["professional_section_titles"],SECTION_LABELS)
  rendered=render_chinese_reading(self.r)
  self.assertEqual(rendered.count("\n## "),10)
  for key in SECTION_ORDER:self.assertIn("## "+SECTION_LABELS[key],rendered)
 def test_approval_guard(self):
  self.assertEqual(self.r["editorial"]["status"],"draft")
  self.assertFalse(self.r["editorial"]["human_approved"])
  with self.assertRaises(PermissionError):
   render_chinese_reading(self.r,draft_preview=False)
if __name__=="__main__":unittest.main()
