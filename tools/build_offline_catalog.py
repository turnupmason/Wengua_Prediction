#!/usr/bin/env python3
"""Build approved Wengua readings into an offline, read-only SQLite release.

Usage:
  python3 tools/build_offline_catalog.py --root . --out build/wengua_readings.sqlite
This is editorial packaging ONLY. It never casts, scores, or edits a reading.
"""
import argparse
import hashlib
import json
import pathlib
import sqlite3

SECTIONS = ("macro", "illness", "doctor", "medicine", "patient",
            "hour", "chief", "gender", "verdict", "timing")
DDL = """
CREATE TABLE IF NOT EXISTS readings (
 record_id TEXT PRIMARY KEY,
 board_key TEXT NOT NULL,
 year TEXT NOT NULL, month TEXT NOT NULL,
 day TEXT NOT NULL, hour TEXT NOT NULL,
 solar_term TEXT NOT NULL, branch TEXT NOT NULL,
 relationship TEXT NOT NULL, consultation_context TEXT NOT NULL,
 natal_mode TEXT NOT NULL,
 grade TEXT NOT NULL, score INTEGER NOT NULL,
 source_evidence_sha TEXT NOT NULL,
 original_text_sha TEXT NOT NULL,
 editorial_version INTEGER NOT NULL,
 banner TEXT NOT NULL, title TEXT NOT NULL,
 first_screen TEXT NOT NULL, professional_json TEXT NOT NULL,
 editorial_sha TEXT NOT NULL,
 UNIQUE (year, month, day, hour, solar_term, branch, relationship,
         consultation_context, natal_mode, source_evidence_sha)
);
CREATE INDEX IF NOT EXISTS idx_readings_lookup
ON readings (board_key,year,month,day,hour,solar_term,branch,
             relationship,consultation_context,natal_mode);
"""

def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def validate(record, path, root):
    assert record["schema_version"] == "wengua_reading_v1"
    src = record["source_context"]
    board = record["physical_chart"]
    lock = record["fact_lock"]
    ed = record["editorial"]
    expected_key = "%s-%02d-%s" % (board["direction"], board["ju"], board["hour_ganzhi"])
    assert board["key"] == expected_key, (path, "bad board key")
    assert board["hour_ganzhi"] == src["hour"]
    assert src["natal_mode"] == "none", "this version deliberately excludes natal"
    stem = "阳遁" if board["direction"] == "yang" else "阴遁"
    expected_dir = (root / "疾病" / "病情程度" / "盘面" / stem /
                    ("%02d局" % board["ju"]) / src["hour"] /
                    {"father":"父亲","mother":"母亲"}.get(src["relationship"], src["relationship"]))
    assert path.parent == expected_dir, (path, "wrong board directory")
    assert src["relationship"] != "father" or (
        lock["patient_symbol"] == "甲" and lock["patient_source_ganzhi"] == "甲子"
        and lock["carrier_stem"] == "戊"
    ), "father 甲子 source must use 甲子→戊 without replacing 甲"
    assert len(lock["original_text_sha256"]) == 64
    assert len(lock["original_evidence_sha256"]) == 64
    assert ed["status"] in ("draft","fact_checked","reviewed","approved","rejected")
    assert isinstance(ed["human_approved"], bool)
    assert set(SECTIONS).issubset(ed["professional_sections"])
    assert all(len(ed["professional_sections"][k].strip()) >= 10 for k in SECTIONS)
    assert ed["front_screen"]["text"].strip()
    if ed["status"] == "approved":
        assert ed["human_approved"] and ed.get("reviewer"), "approved must be signed"
    else:
        assert not ed["human_approved"], "draft cannot be marked approved"
    return ed["status"] == "approved"

def build(root, out):
    root, out = pathlib.Path(root).resolve(), pathlib.Path(out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    # Refuse silent overwrite of a published bundle.
    if out.exists():
        raise FileExistsError("offline catalogue already exists: %s" % out)
    paths = sorted((root/"疾病"/"病情程度"/"盘面").rglob("case-*.json"))
    db = sqlite3.connect(out)
    count = 0
    statuses = {}
    board_counts = {}
    try:
        db.executescript(DDL)
        for path in paths:
            record = json.loads(path.read_text(encoding="utf-8"))
            ed, src, lock, board = (record[k] for k in
                ("editorial", "source_context", "fact_lock", "physical_chart"))
            approved = validate(record, path, root)
            statuses[ed["status"]] = statuses.get(ed["status"], 0) + 1
            if not approved:
                continue
            front = ed["front_screen"]
            editorial_sha = hashlib.sha256(canonical_json(ed).encode("utf-8")).hexdigest()
            db.execute("""INSERT INTO readings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                record["record_id"],board["key"],src["year"],src["month"],src["day"],
                src["hour"],src["solar_term"],src["solar_term_branch"],
                src["relationship"],src["consultation_context"],src["natal_mode"],
                lock["grade"],lock["score"],lock["original_evidence_sha256"],
                lock["original_text_sha256"],ed["version"],front["banner"],
                front["title"],front["text"],canonical_json(ed["professional_sections"]),
                editorial_sha))
            count += 1
            board_counts[board["key"]] = board_counts.get(board["key"],0)+1
        db.commit()
    except BaseException:
        db.close()
        out.unlink(missing_ok=True)
        raise
    db.close()
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    manifest = {"schema":"wengua_offline_reading_release_v1",
                "approved_count":count,"review_status_counts":statuses,
                "board_count":len(board_counts),"sqlite_sha256":digest,
                "source_repo":"turnupmason/Wengua_Prediction",
                "requires_exact_source_match":True,"natal_mode":"none",
                "note":"SQLite created only from human-signed approved readings; no online fetch."}
    out.with_suffix(".manifest.json").write_text(
        json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return manifest

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root",default=".")
    parser.add_argument("--out",default="build/wengua_readings.sqlite")
    args = parser.parse_args()
    print(json.dumps(build(args.root,args.out),ensure_ascii=False,indent=2))
