#!/usr/bin/env python3
"""Style and source safety checks for fresh, case-specific health prose."""
from __future__ import annotations
import json
import pathlib
import re
ROOT=pathlib.Path(__file__).resolve().parents[1]
BOARD=ROOT/"疾病"/"病情程度"/"盘面"
KEYS={"macro","illness","patient","doctor","medicine","hour","chief","gender","verdict","timing"}
BAD=("生门","死门","值符","天芮","丁奇","白虎","天心","乙奇","玄武",
     "伏吟","反吟","坤二","艮八","乾六","兑七","macro","illness",
     "取吉","冻结结果","源力量","势待核","首先","其次","综上所述",
     "此局偏吉","先看病的这一头","代表病情的部分")

ACCOUNTING = ("重复记分","重复计分","计分","宫分","评分","分数","加分","叠分","重复计算","重复算","重复加力","只计一次","只算一次","冻判","冻结","score","源强","源力量")

def run():
    assert not (ROOT/"staging").exists(),"obsolete staging must be removed"
    paths=sorted(BOARD.rglob("case-*.json"))
    assert paths,"new draft missing"
    ids=set()
    for path in paths:
        r=json.loads(path.read_text(encoding="utf-8")); e=r["editorial"]
        assert re.fullmatch(r"case-\d{6}-jieqi-a\.v(?:9|[1-9]\d+)\.json",path.name),path
        assert e["version"]>=9 and e["status"] in ("draft","fact_checked","reviewed","approved","rejected")
        assert not e["human_approved"] or (e["status"]=="approved" and e.get("reviewer"))
        assert set(e["professional_sections"])==KEYS
        assert set(e["professional_section_titles"])==KEYS
        assert all(len(x.strip())>=20 for x in e["professional_sections"].values()),("empty professional evidence",path)
        assert all(any("\u4e00"<=c<="\u9fff" for c in x) for x in e["professional_section_titles"].values())
        front=e["front_screen"]["text"]
        assert 240<=len(front)<=1100,(path,"length",len(front))
        assert not any(term in front for term in BAD),(path,"jargon/filler")
        assert "？" not in front and "?" not in front
        assert "病情" in front and "医生" in front and "药物" in front
        visible = front + "\\n" + "\\n".join(e["professional_sections"].values())
        assert not any(term in visible for term in ACCOUNTING), ("internal computation leaked to reader", path)
        assert len(r["fact_lock"]["original_evidence_sha256"])==64
        assert len(r["fact_lock"]["original_text_sha256"])==64
        assert r["record_id"] not in ids
        ids.add(r["record_id"])
    print("PASS fresh Chinese prose",len(paths),"no old drafts/staging; no internal jargon in front screen")
if __name__=="__main__":run()
