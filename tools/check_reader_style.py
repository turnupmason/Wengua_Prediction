#!/usr/bin/env python3
"""Release/editorial quality gate. Must not confuse unique SHA with professional prose."""
import collections,json,pathlib,re,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
BOARD=ROOT/"疾病"/"病情程度"/"盘面"
BAN=("此局偏吉","并非病宫处处顺利","为什么这盘","先看病的这一头",
     "代表病情的部分","几处条件合在一起","仍依原局取",
     "首先","其次","综上所述","这盘的关键")
CHAPTERS={"macro","illness","patient","doctor","medicine","hour","chief","gender","verdict","timing"}
def run():
    old=sorted(BOARD.rglob("case-*-jieqi-a.v5.json"))
    assert len(old)==6000,("v5 missing",len(old))
    ids=set()
    for path in old:
        r=json.loads(path.read_text(encoding="utf-8"))
        n=r["source_context"]["scenario_id"]
        assert n not in ids
        ids.add(n)
        assert r["editorial"]["status"]=="rejected",(path,r["editorial"]["status"])
        assert not r["editorial"]["human_approved"]
    assert ids==set(range(1,6001))
    new=sorted(BOARD.rglob("case-*-jieqi-a.v6.json"))
    assert new, "no updated professionally edited examples"
    prefixes=collections.Counter()
    for path in new:
        x=json.loads(path.read_text(encoding="utf-8"))
        n=x["source_context"]["scenario_id"]
        p=path.with_name(path.name.replace(".v6.json",".v5.json"))
        assert p.exists()
        oldx=json.loads(p.read_text(encoding="utf-8"))
        for section in ("physical_chart","source_context","fact_lock"):
            assert x[section]==oldx[section],(n,section,"source data changed")
        assert x["editorial"]["status"]=="draft" and x["editorial"]["human_approved"] is False
        assert x["editorial"]["version"]==6
        sec=x["editorial"]["professional_sections"]
        assert set(sec)==CHAPTERS,(n,set(sec))
        front=x["editorial"]["front_screen"]["text"]
        assert 50<=len(front)<=220,(n,"length",len(front))
        text="\n".join([front,*sec.values()])
        for word in BAN:assert word not in text,(n,word)
        assert not any(q in text for q in ["？","?"]),(n,"questions")
        assert not re.search("甲势(?:极|大|中|小)|乙势(?:极|大|中|小)|宫象(?:极|大|中|小)",text),(n,"power narration")
        prefixes[front[:12]]+=1
    assert max(prefixes.values())<=2,("repeated lead",prefixes.most_common(1))
    print(f"REJECTED v5: {len(old)}/6000; curated v6: {len(new)} PASS, no questions/banned openers, immutable evidence")
if __name__=="__main__":
    try:run()
    except (AssertionError, ValueError) as ex:
        print("EDITORIAL FAILURE",ex,file=sys.stderr);sys.exit(1)
