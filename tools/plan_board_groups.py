#!/usr/bin/env python3
"""Plan board-group destinations from BigFish editorial JSONL or condensed CSV.
Never edits raw records or declares GPT drafts approved.
Examples:
 python3 tools/plan_board_groups.py --input father_xxx_待审事实包.jsonl --out /tmp/plan
 python3 tools/plan_board_groups.py --input father_6000_jieqi_a_review_index.csv --out /tmp/plan
"""
import argparse
import csv
import hashlib
import json
import pathlib
import re
from collections import Counter

BOARD = re.compile(r"^(yang|yin)-(0[1-9])-(.{2})$")
BUREAU = re.compile(r"^(阳|阴)([1-9])局")
RELATION_DIR = {"father":"父亲","mother":"母亲","younger_sibling":"弟弟"}

def plan_path(board, relation, serial, branch):
    m=BOARD.fullmatch(board)
    if not m:
        raise ValueError("invalid physical board id: "+repr(board))
    dun, ju, hour = m.groups()
    return (pathlib.Path("疾病")/"病情程度"/"盘面"/
            ("阳遁" if dun=="yang" else "阴遁")/(ju+"局")/
            hour / RELATION_DIR.get(relation,relation) /
            ("case-%06d-jieqi-%s.v1.json" % (int(serial),branch))).as_posix()

def from_csv(path):
    with path.open(newline="",encoding="utf-8-sig") as fp:
        for row in csv.DictReader(fp):
            serial=row["序号"]
            label=row["起局甲"]
            m=BUREAU.match(label)
            if not m:
                raise ValueError("unrecognized bureau: "+label)
            dun="yang" if m.group(1)=="阳" else "yin"
            board="%s-%02d-%s" % (dun,int(m.group(2)),row["时柱"])
            yield {"serial":serial,"case_identity":serial,"board":board,
                   "branch":"a","term":row["节气甲"],
                   "relation":"father","year":row["年柱"],
                   "month":row["月柱"],"day":row["日柱"],
                   "hour":row["时柱"],"grade":row["原等级甲"],
                   "original_sha":row.get("原文SHA256",""),
                   "evidence_sha":row.get("原证据SHA","")}

def from_jsonl(path):
    with path.open(encoding="utf-8") as fp:
        for line in fp:
            if not line.strip():
                continue
            item=json.loads(line)
            if item.get("schema")!="wengua_v80_v102_bigfish_editorial_precompute_v1":
                raise ValueError("unknown input schema")
            if item.get("branch")!="甲":
                continue
            lock=item["original_result"]
            if not lock.get("original_text") or str(lock.get("status","")).startswith("失败"):
                continue
            identity=item["immutable_identity"]
            pillars=identity["four_pillars"]
            yield {"serial":identity["index"],"case_identity":item["case_id"],
                   "board":lock["physical_board_id"],"branch":"a",
                   "term":identity["term"],"relation":identity["relationship"],
                   "year":pillars["year"],"month":pillars["month"],
                   "day":pillars["day"],"hour":pillars["hour"],
                   "grade":lock["grade"],
                   "original_sha":lock.get("original_text_sha256",""),
                   "evidence_sha":lock.get("source_evidence_sha256","")}

def build_index(source, output):
    source,output=pathlib.Path(source),pathlib.Path(output)
    output.mkdir(parents=True,exist_ok=True)
    rows=from_csv(source) if source.suffix.lower()==".csv" else from_jsonl(source)
    grouped=Counter()
    ids=set()
    result=[]
    for r in rows:
        dest=plan_path(r["board"],r["relation"],r["serial"],r["branch"])
        identity=(r["relation"],r["serial"],r["branch"],r["case_identity"])
        if identity in ids:
            raise ValueError("duplicate case identity: "+str(identity))
        ids.add(identity)
        grouped[r["board"]]+=1
        result.append({**r,"target_path":dest,"status":"not_approved"})
    index_path=output/"planned_destinations.csv"
    with index_path.open("w",newline="",encoding="utf-8-sig") as f:
        writer=csv.DictWriter(f,fieldnames=[
          "serial","case_identity","board","branch","term","relation",
          "year","month","day","hour","grade","original_sha",
          "evidence_sha","target_path","status"])
        writer.writeheader()
        writer.writerows(result)
    manifest={"schema":"wengua_physical_board_group_plan_v1",
              "source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),
              "records":len(result),"board_keys":len(grouped),
              "group_counts":dict(sorted(grouped.items())),
              "branch":"a","all_records_status":"not_approved"}
    (output/"board_groups.json").write_text(
        json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return manifest

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--input",required=True)
    p.add_argument("--out",required=True)
    opt=p.parse_args()
    summary=build_index(opt.input,opt.out)
    print("planned %d source cases into %d physical boards (all unapproved)"
          % (summary["records"],summary["board_keys"]))
