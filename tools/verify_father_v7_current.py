#!/usr/bin/env python3
"""Read full v7 catalogue and compare every case with preserved rejected v5 immutable facts.
Allows natural repetition in the 1080 physical chart space; never mistakes local auspices
for the summed V8.0 result and never authorizes an iOS release.
"""
import pathlib,json,re,collections
ROOT=pathlib.Path(__file__).resolve().parents[1]/"疾病"/"病情程度"/"盘面"
SCORES={"极大吉":5,"大吉":4,"中吉":3,"小吉":2,"极小吉":1,"微恙":0,"极小凶":-1,"小凶":-2,"中凶":-3,"大凶":-4,"极大凶":-5}
CHAPTERS={"macro","illness","patient","doctor","medicine","hour","chief","gender","verdict","timing"}
BAN=("此局偏吉","并非病宫处处顺利","为什么这盘","先看病的这一头","代表病情的部分","综上所述")
def main():
    current=sorted(ROOT.rglob("case-*-jieqi-a.v7.json"))
    assert len(current)==6000,("new-case count",len(current))
    cases=set();boards=set();fronts=collections.Counter()
    for p in current:
        d=json.loads(p.read_text(encoding="utf-8"))
        source=d["source_context"];lock=d["fact_lock"];ed=d["editorial"]
        idx=source["scenario_id"]
        assert idx not in cases,("duplicate case",idx)
        cases.add(idx);boards.add(d["physical_chart"]["key"])
        before=p.with_name(p.name.replace(".v7.json",".v5.json"))
        assert before.is_file(),idx
        old=json.loads(before.read_text(encoding="utf-8"))
        assert old["editorial"]["status"]=="rejected",idx
        for field in ("source_context","physical_chart","fact_lock"):
            assert d[field]==old[field],(idx,field)
        assert lock["score"]==SCORES[lock["grade"]],idx
        assert ed["version"]==7 and ed["status"]=="draft" and ed["human_approved"] is False,idx
        assert ed["front_screen"]["title"].startswith(lock["grade"]+"："),idx
        assert set(ed["professional_sections"])==CHAPTERS and all(len(s)>=10 for s in ed["professional_sections"].values()),idx
        intro=ed["front_screen"]["text"];whole=intro+"\n"+"\n".join(ed["professional_sections"].values())
        assert 40<=len(intro)<=180 and "？" not in whole and "?" not in whole,idx
        assert all(x not in whole for x in BAN),idx
        fronts[intro]+=1
    assert cases==set(range(1,6001))
    assert len(boards)==900,("group count",len(boards))
    print("PASS v7=6000 preserved-v5=6000 group-keys=900 grade-score/fact-lock unchanged")
    print("distinct front wording %d / 6000; repeat is legitimate for actual same facts, NOT a rejection criterion"%len(fronts))
if __name__=="__main__":main()
