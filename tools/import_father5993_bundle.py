#!/usr/bin/env python3
"""Import the first-volume draft archive's case JSON into this repository.

EXPLICIT USER-SIDE IMPORT: this script does not approve or publish any draft.
Source archives containing unapproved original readings stay outside public Git.
Usage:
    python3 tools/import_father5993_bundle.py \
      '/path/to/Wengua_父亲正式首卷_其余5993长篇候选_完整审稿包_v3.zip'
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, zipfile
ARCHIVE_SHA="9d85d0aafa356cd472f48ed0628fb331e69eb2f3580d5a7ff8b260541d59e8a1"
CASE=re.compile(r"^疾病/病情程度/盘面/(阴遁|阳遁)/(0[1-9])局/([^/]+)/父亲/case-(\d{6})-jieqi-a\.v3\.json$")
EXCEPTIONS={1,2,20,42,3000,4201,6000}
def import_bundle(bundle,repo_root):
    bundle=pathlib.Path(bundle).resolve()
    repo_root=pathlib.Path(repo_root).resolve()
    digest=hashlib.sha256(bundle.read_bytes()).hexdigest()
    if digest!=ARCHIVE_SHA:
        raise ValueError("unrecognized bundle checksum; refuse import")
    prepared=[]
    with zipfile.ZipFile(bundle) as z:
        for member in z.infolist():
            name=member.filename
            m=CASE.fullmatch(name)
            if not m:continue
            serial=int(m.group(4))
            if serial in EXCEPTIONS:raise ValueError("must preserve exemplar: "+name)
            data=json.loads(z.read(member))
            if data["editorial"]["status"]!="draft" or data["editorial"]["human_approved"]:
                raise ValueError("bad approval state: "+name)
            if data["fact_lock"]["grade"] !=data["editorial"]["first_screen"]["title"].split("：")[0]:
                raise ValueError("grade drift: "+name)
            if data["source_context"]["solar_term_branch"]!="a" or data["source_context"]["natal_mode"]!="none":
                raise ValueError("wrong conditions: "+name)
            if data["physical_chart"]["hour_ganzhi"]!=m.group(3):
                raise ValueError("wrong board group: "+name)
            if len(data["editorial"]["professional_sections"])!=10:
                raise ValueError("missing professional chapters: "+name)
            dest=repo_root/pathlib.PurePosixPath(name)
            if dest.exists():raise FileExistsError("preserve existing manual draft: "+name)
            prepared.append((dest,z.read(member)))
    if len(prepared)!=5993:raise ValueError("expected 5993 independent v3 records, got %s"%len(prepared))
    for dest,body in prepared:
        dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(body)
    print("imported 5993 versioned DRAFT JSONs; all pending manual approval")
    return 5993
if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("archive")
    parser.add_argument("--repo-root",default=".")
    args=parser.parse_args()
    import_bundle(args.archive,args.repo_root)
