#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plan high-volume literary editing from WenguaApp's original BigFish JSONL.

A planner, NOT a language model, evaluator, or publisher. Run on the user's
Mac with the real source JSONL + 1080 physical board cache. It never changes
V8 scores and never reuses rejected editorial prose.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import sqlite3
import sys
import zlib
from collections import Counter, defaultdict

SCHEMA = "wengua_v80_v102_bigfish_editorial_precompute_v1"
BOARD_RE = re.compile(r"^(?:yang|yin)-0[1-9]-.{2}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
SCORES = {"极大吉": 5, "大吉": 4, "中吉": 3, "小吉": 2, "极小吉": 1,
          "微恙": 0, "极小凶": -1, "小凶": -2, "中凶": -3,
          "大凶": -4, "极大凶": -5}
BRANCHES = {"甲": "a", "乙": "b"}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def hash_file(path):
    h = hashlib.sha256()
    with path.open("rb") as fp:
        for block in iter(lambda: fp.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def source_files(inp):
    if inp.is_file():
        return [inp]
    if not inp.is_dir():
        raise ValueError("Input must be a JSONL file or directory: " + str(inp))
    # WenguaApp's exact output suffix; do not accidentally read editorial output.
    files = sorted(inp.rglob("*_待审事实包.jsonl"))
    if not files:
        files = sorted(p for p in inp.rglob("*.jsonl")
                       if not p.name.startswith(("failures", "batch_")))
    if not files:
        raise ValueError("No source JSONL found in " + str(inp))
    return files


def ensure_source_record(obj, desired_branch):
    if obj.get("schema") != SCHEMA:
        raise ValueError("source schema mismatch")
    if obj.get("branch") != desired_branch:
        return None
    identity = obj.get("immutable_identity") or {}
    result = obj.get("original_result") or {}
    four = identity.get("four_pillars") or {}
    idx = identity.get("index")
    if not isinstance(idx, int) or idx < 1:
        raise ValueError("missing positive source index")
    if identity.get("relationship") is None:
        raise ValueError("missing relationship")
    if any(not four.get(part) for part in ("year", "month", "day", "hour")):
        raise ValueError("incomplete four pillars")
    board = result.get("physical_board_id")
    if not isinstance(board, str) or not BOARD_RE.fullmatch(board):
        raise ValueError("missing or invalid physical BigFish board id")
    grade, score = result.get("grade"), result.get("score_internal")
    if grade not in SCORES or score != SCORES[grade]:
        raise ValueError("invalid or inconsistent frozen grade/score")
    for field in ("original_text_sha256", "source_evidence_sha256"):
        if not SHA_RE.fullmatch(result.get(field) or ""):
            raise ValueError("missing source SHA: " + field)
    fact_lock = result.get("frozen_fact_lock")
    if not isinstance(fact_lock, dict) or not fact_lock.get("selected_roles"):
        raise ValueError("frozen role/palace facts missing")
    if fact_lock.get("original_physical_board_id") != board:
        raise ValueError("original board ID differs from frozen role lock")
    # All condition-specific facts remain in each record. Do not group text
    # purely by board, grade, or a single role palace.
    case = {
        "case_id": obj.get("case_id"),
        "immutable_identity": identity,
        "branch": desired_branch,
        "physical_board_id": board,
        "physical_board_json": result.get("physical_board_json"),
        "original_grade": grade,
        "original_score_internal": score,
        "original_text_sha256": result["original_text_sha256"],
        "source_evidence_sha256": result["source_evidence_sha256"],
        "frozen_fact_lock": fact_lock,
        "source_sections": result.get("sections", []),
        "editorial_status": "draft_not_approved",
    }
    # Signature = clustering hint, never authorization to copy text.
    # Includes actual role factors, source powers, macro and the condition
    # under which they were evaluated.
    signature_fields = {
        "board": board, "term": identity.get("term"),
        "month_ganzhi": four["month"], "relationship": identity["relationship"],
        "grade": grade, "score": score,
        "roles": fact_lock.get("selected_roles"),
        "gates": fact_lock.get("role_effectiveness_gates"),
        "role_reviews": fact_lock.get("role_group_reviews"),
        "verdict": fact_lock.get("verdict"),
        "macro": fact_lock.get("macro_fuyin_fanyin"),
        "first_stage": fact_lock.get("first_stage_macro"),
        "person_binding": fact_lock.get("person_binding"),
    }
    case["similarity_signature"] = digest(signature_fields)
    case["source_record_sha256"] = digest(obj)
    return case


def connect(path):
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS case_queue (
        relationship TEXT NOT NULL, branch TEXT NOT NULL,
        case_idx INTEGER NOT NULL, board TEXT NOT NULL,
        signature TEXT NOT NULL, grade TEXT NOT NULL,
        source_sha TEXT NOT NULL, data_zlib BLOB NOT NULL,
        PRIMARY KEY (relationship, branch, case_idx)
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS board_cases ON case_queue(board, signature, case_idx)")
    db.execute("""CREATE TABLE IF NOT EXISTS failures (
        source_file TEXT NOT NULL, source_line INTEGER NOT NULL,
        reason TEXT NOT NULL, record_sha TEXT NOT NULL,
        PRIMARY KEY(source_file, source_line)
    )""")
    return db


def stage(db, files, branch, limit):
    counts = Counter()
    seen = 0
    for source in files:
        with source.open("r", encoding="utf-8-sig") as stream:
            for line_num, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                    case = ensure_source_record(obj, branch)
                    if case is None:
                        counts["other_term_skipped"] += 1
                        continue
                    idx = case["immutable_identity"]["index"]
                    rel = case["immutable_identity"]["relationship"]
                    existing = db.execute(
                        "SELECT source_sha FROM case_queue WHERE relationship=? AND branch=? AND case_idx=?",
                        (rel, branch, idx)).fetchone()
                    if existing:
                        if existing[0] != case["source_record_sha256"]:
                            raise ValueError("source identity collision with different evidence")
                        counts["already_staged"] += 1
                        continue
                    packed = zlib.compress(canonical(case).encode("utf-8"), level=6)
                    db.execute("INSERT INTO case_queue VALUES(?,?,?,?,?,?,?,?)",
                               (rel, branch, idx, case["physical_board_id"],
                                case["similarity_signature"], case["original_grade"],
                                case["source_record_sha256"], packed))
                    counts["new_drafts_queued"] += 1
                    seen += 1
                    if seen % 1000 == 0:
                        db.commit()
                    if limit and seen >= limit:
                        db.commit()
                        return counts
                except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                    record_sha = hashlib.sha256(line.encode("utf-8")).hexdigest()
                    db.execute("INSERT OR IGNORE INTO failures VALUES(?,?,?,?)",
                               (str(source), line_num, str(exc), record_sha))
                    counts["failed_source_facts"] += 1
        db.commit()
    db.commit()
    return counts


def validate_boards(db, boards_root):
    present = {}
    missing = []
    for (board,) in db.execute("SELECT DISTINCT board FROM case_queue ORDER BY board"):
        file = boards_root / (board + ".json")
        if not file.is_file():
            missing.append(board)
            continue
        try:
            with file.open(encoding="utf-8") as f:
                payload = json.load(f)
            if not isinstance(payload, dict) or payload.get("physical_id") != board:
                raise ValueError("wrong BigFish physical ID")
            if payload.get("hour_ganzhi") != board[-2:] or payload.get("dun") != board.split("-")[0]:
                raise ValueError("wrong BigFish hour/direction")
            if not isinstance(payload.get("palaces"), (dict, list)) or len(payload["palaces"]) != 9:
                raise ValueError("missing nine genuine palaces")
            if not isinstance(payload.get("source_original_raw"), dict):
                raise ValueError("missing upstream BigFish source chart")
            present[board] = {"path": str(file.resolve()), "sha256": hash_file(file)}
        except (ValueError, UnicodeDecodeError, OSError):
            missing.append(board)
    return present, missing


def safe_write(file, body):
    file.parent.mkdir(parents=True, exist_ok=True)
    payload = body.encode("utf-8")
    if file.exists():
        if file.read_bytes() != payload:
            raise FileExistsError("Refusing to overwrite an existing batch: " + str(file))
        return False
    tmp = file.with_name(file.name + ".incomplete")
    with tmp.open("xb") as f:
        f.write(payload)
    tmp.replace(file)
    return True


def export(db, output, board_profiles, batch_size, branch, source_count, stage_stats):
    if not 1 <= batch_size <= 1000:
        raise ValueError("batch-size must be 1..1000")
    output.mkdir(parents=True, exist_ok=True)
    batches = []
    boards = Counter()
    grades = Counter()
    signatures = set()
    active_board = None
    buffer = []
    part = 0

    def flush(board, items, sequence):
        if not items:
            return
        d = "batches/" + board + "/batch_" + ("%04d" % sequence) + ".jsonl"
        content = "".join(canonical(item) + "\n" for item in items)
        safe_write(output / d, content)
        batches.append({"path": d, "board": board,
                        "rows": len(items), "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                        "first_case": items[0]["immutable_identity"]["index"],
                        "last_case": items[-1]["immutable_identity"]["index"]})

    query = """SELECT board,signature,grade,data_zlib FROM case_queue
               ORDER BY board, signature, relationship, case_idx"""
    for board, signature, grade, packed in db.execute(query):
        if board != active_board:
            if buffer:
                part += 1
                flush(active_board, buffer, part)
            active_board, buffer, part = board, [], 0
        case = json.loads(zlib.decompress(packed))
        case["board_source"] = board_profiles[board]
        case["release_status"] = "draft_not_approved"
        buffer.append(case)
        boards[board] += 1
        grades[grade] += 1
        signatures.add(signature)
        if len(buffer) >= batch_size:
            part += 1
            flush(board, buffer, part)
            buffer = []
    if buffer:
        part += 1
        flush(active_board, buffer, part)
    failures = db.execute("SELECT COUNT(*) FROM failures").fetchone()[0]
    manifesto = {
        "schema": "wengua_bigfish_1080_board_editorial_batches_v1",
        "branch": branch, "source_files_seen": source_count,
        "queued_independent_cases": sum(boards.values()),
        "distinct_physical_board_groups": len(boards),
        "distinct_similar_evidence_signatures": len(signatures),
        "batches": len(batches), "batch_size_limit": batch_size,
        "grade_counts": dict(sorted(grades.items())),
        "board_counts": dict(sorted(boards.items())),
        "stage_is_idempotent": True,
        "retained_failure_records": failures,
        "all_queued_status": "draft_not_approved",
        "app_approved_count": 0,
        "v8_frozen_score_modified": False,
        "literary_text_generated": False,
        "no_rejected_editorial_prose_reused": True,
        "batch_index": batches,
    }
    safe_write(output / "batch_manifest.json", json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n")
    return manifesto


def main(argv=None):
    ap = argparse.ArgumentParser(description="Group existing 518400 BigFish facts into evidence-safe literary batches")
    ap.add_argument("--input", required=True, type=pathlib.Path, help="Source JSONL file or Excel_CSV_可直接打开 directory")
    ap.add_argument("--boards-root", required=True, type=pathlib.Path, help="Real BigFish physical_1080/ JSON directory")
    ap.add_argument("--out", required=True, type=pathlib.Path, help="New local folder for manifest, SQLite and batch JSONL")
    ap.add_argument("--branch", choices=sorted(BRANCHES), default="甲", help="Only 甲 is active for the current editing stage")
    ap.add_argument("--batch-size", type=int, default=200)
    ap.add_argument("--max-new", type=int, default=0, help="Optional small pilot; 0 = all available source records")
    args = ap.parse_args(argv)
    if args.branch != "甲":
        ap.error("Current literary scope is only 节气甲; 节气乙 is not approved for editing")
    files = source_files(args.input)
    args.out.mkdir(parents=True, exist_ok=True)
    db = connect(args.out / "editorial_queue.sqlite")
    stats = stage(db, files, args.branch, args.max_new)
    print("source staging:", canonical(dict(stats)), file=sys.stderr)
    profiles, missing = validate_boards(db, args.boards_root)
    if missing:
        (args.out / "missing_original_boards.json").write_text(
            json.dumps(missing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("STOP: missing/invalid original BigFish physical boards:", len(missing), file=sys.stderr)
        return 2
    result = export(db, args.out, profiles, args.batch_size, args.branch, len(files), stats)
    print("PASS", canonical({k: result[k] for k in (
        "queued_independent_cases", "distinct_physical_board_groups",
        "distinct_similar_evidence_signatures", "batches",
        "app_approved_count", "literary_text_generated")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
