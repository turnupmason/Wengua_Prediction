#!/usr/bin/env python3
"""Honor user rejection of all father Jieqi-A v5 prose without altering source facts."""
import json, pathlib, hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
TARGET=ROOT/"疾病"/"病情程度"/"盘面"
REASON="用户于2026-10-29明确否决全部v5：固定开头、疑问句、重复套话、冗长且不专业。该稿不得恢复为候选成品。"
def run():
    files=sorted(TARGET.rglob("case-*-jieqi-a.v5.json"))
    if len(files)!=6000:raise RuntimeError(f"expected exactly 6000 old records, found {len(files)}")
    seen=set(); changed=0
    for f in files:
        d=json.loads(f.read_text(encoding="utf-8"))
        n=d["source_context"]["scenario_id"]
        if n in seen:raise AssertionError("duplicate case "+str(n))
        seen.add(n)
        if d["editorial"]["human_approved"]:raise AssertionError("approved v5 must not be silently demoted")
        frozen=hashlib.sha256(json.dumps(d["fact_lock"],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        prior=d["editorial"]["status"]
        if prior not in ("draft","rejected"):raise AssertionError((f,prior))
        if prior=="draft":
            d["editorial"]["status"]="rejected"
            d["editorial"]["human_approved"]=False
            d["editorial"]["rejection_reason"]=REASON
            d["editorial"]["rejected_version_preserved"]=True
            assert frozen==hashlib.sha256(json.dumps(d["fact_lock"],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            f.write_text(json.dumps(d,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            changed+=1
    assert seen==set(range(1,6001))
    print(f"marked all 6000 v5 REJECTED, updated {changed}; original fact locks and texts unchanged")
if __name__=="__main__":run()
