"""평가셋 점검: 형식, 문항 수, 개발/검증 분리, 정답 키가 DB에 실제로 있는지 확인한다(DB 읽기만 함).

실행(저장소 최상위 폴더에서):
  uv run --project backend python eval/validate_dataset.py
DATABASE_URL은 backend/.env 에서 읽는다. 키·비밀번호는 출력하지 않는다.
"""
import json
import sys
from collections import Counter
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from load_to_db import clean_url, read_env  # noqa: E402

DS = ROOT / "eval" / "datasets" / "v1"
EXPECT_MATCH = {"colloquial": 16, "typo_spacing": 8, "quantity": 10, "multi_spec": 10, "other_muni": 8, "vague_unmatched": 12}
EXPECT_SPLIT = {"matching": {"dev": 45, "test": 19}, "procedure": {"dev": 11, "test": 5}}
STATUS = {"matched", "ambiguous", "unmatched"}


def load(name):
    return [json.loads(l) for l in (DS / name).read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> int:
    errors = []
    m, p = load("matching.jsonl"), load("procedure.jsonl")
    ids = [c["case_id"] for c in m + p]
    if len(ids) != len(set(ids)):
        errors.append("case_id 중복")
    got = dict(Counter(c["category"] for c in m))
    if got != EXPECT_MATCH:
        errors.append(f"매칭 구분별 문항 수 불일치: {got}")
    for layer, rows in (("matching", m), ("procedure", p)):
        s = dict(Counter(c["split"] for c in rows))
        if s != EXPECT_SPLIT[layer]:
            errors.append(f"{layer} 분리 불일치: {s}")
    if len(p) != 16:
        errors.append(f"절차 문항 수 {len(p)}")

    url = read_env(ROOT / "backend" / ".env").get("DATABASE_URL", "")
    keys = set()
    if url:
        with psycopg.connect(clean_url(url)) as conn:
            keys = {f"{c}|{n}|{s}" for c, n, s in conn.execute(
                "SELECT municipality_code, name, spec FROM waste_items").fetchall()}
    else:
        print("DATABASE_URL이 없어 정답 키 존재 확인은 건너뜁니다.")

    for c in m:
        if not c["input"].strip() or len(c["input"]) > 500:
            errors.append(f"{c['case_id']}: 입력 길이")
        for e in c["expected"]:
            if e["status"] not in STATUS or not (1 <= e["quantity"] <= 99):
                errors.append(f"{c['case_id']}: 상태·수량 값")
            if e["status"] == "unmatched" and e["gold"]:
                errors.append(f"{c['case_id']}: unmatched인데 정답이 있음")
            if e["status"] != "unmatched" and not e["gold"]:
                errors.append(f"{c['case_id']}: 정답 없음")
            if e["status"] == "matched" and not any(g["grade"] == 2 for g in e["gold"]):
                errors.append(f"{c['case_id']}: matched인데 grade 2 정답 없음")
            for g in e["gold"]:
                if not g["gold_key"].startswith(c["municipality_code"] + "|"):
                    errors.append(f"{c['case_id']}: 다른 지자체 정답 키 {g['gold_key']}")
                if keys and g["gold_key"] not in keys:
                    errors.append(f"{c['case_id']}: DB에 없는 정답 키 {g['gold_key']}")
    for c in p:
        if c["kind"] not in ("answerable", "unanswerable", "unsupported"):
            errors.append(f"{c['case_id']}: kind")
        if c["kind"] == "answerable" and not c["gold_sources"]:
            errors.append(f"{c['case_id']}: 근거 위치 없음")

    print(f"매칭 {len(m)}문항, 절차 {len(p)}문항 / 구분별 {got}")
    if errors:
        print("문제 %d건:" % len(errors))
        for e in errors:
            print(" -", e)
        return 1
    print("평가셋 점검 통과")
    return 0


if __name__ == "__main__":
    sys.exit(main())
