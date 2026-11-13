"""전국 표준데이터 + 성남시 별표 CSV -> 적재용 CSV 4종과 점검 리포트.

사용:
  python scripts/prepare_data.py --national data/raw/national_fees.csv \
      --seongnam data/processed/seongnam_fees.csv --misc data/processed/seongnam_fees_misc.csv

출력(data/processed/): municipalities.csv, item_catalog.csv, waste_items.csv
리포트: docs/research/data_check.md
원칙(PRD 8.2): 근거 없이 채우거나 삭제하지 않는다.
  - 규격 빈칸 -> "규격 미기재"로 보존
  - 수수료 0원 -> 제외하지 않고 fee_type(free/exempt)으로 구분
  - 완전히 같은 행만 중복 제거, 단가가 다른 중복은 둘 다 보존하고 리포트
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SYNONYMS = {k: v for k, v in json.loads((ROOT / "data" / "synonyms.json").read_text(encoding="utf-8")).items() if not k.startswith("_")}
SPEC_MISSING = "규격 미기재"
SEONGNAM_CODE = "3780000"  # 행정기관코드 추정값 [검증 필요]
SEONGNAM_NAME = "경기도 성남시"
SEONGNAM_BASE_DATE = "2026-11-13"  # 데이터 확인일 (PDF에 기준일 표기 없음)
SEONGNAM_LEGAL_DATE = "2026-10-26"  # 조례 시행일
OK_STATUS = {"자동대조완료", "검수완료"}


def read_csv(path):
    for enc in ("utf-8-sig", "cp949"):
        try:
            with open(path, newline="", encoding=enc) as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise ValueError("인코딩을 읽을 수 없습니다: " + str(path))


def clean(text):
    return re.sub(r"\s+", " ", (text or "")).strip()


TIDIED = {"count": 0}


def tidy(text):
    """글자 사이를 한 칸씩 띄운 표기("냉 장 고", "T V")만 붙인다. 그 외 표기는 그대로 둔다."""
    t = clean(text)
    parts = t.split(" ")
    if len(parts) >= 2 and all(len(p) == 1 for p in parts):
        TIDIED["count"] += 1
        return "".join(parts)
    return t


def canonical(text):
    """공백 제거·소문자 후 동의어 사전(data/synonyms.json)을 적용한다."""
    t = re.sub(r"\s+", "", clean(text)).lower()
    for variant in sorted(SYNONYMS, key=len, reverse=True):
        t = t.replace(variant, SYNONYMS[variant])
    return t


def norm_key(text):
    """검색·중복 제거용 정규화 키: 공백 제거, 소문자."""
    return re.sub(r"\s+", "", clean(text)).lower()


def to_int(text):
    t = clean(text).replace(",", "")
    return int(t) if t.isdigit() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--national", required=True)
    ap.add_argument("--seongnam", required=True)
    ap.add_argument("--misc", required=True)
    ap.add_argument("--out", default="data/processed")
    ap.add_argument("--report", default="docs/research/data_check.md")
    a = ap.parse_args()

    items = []  # dict: code,name,category,item_name,spec,fee_won,fee_type,source,base_date
    skipped = Counter()

    # 1) 전국 표준데이터
    for r in read_csv(a.national):
        fee = to_int(r.get("수수료"))
        name = tidy(r.get("대형폐기물명"))
        if fee is None or not name:
            skipped["수수료 또는 품목명 없음"] += 1
            continue
        free = clean(r.get("유무료여부")) == "무료" or fee == 0
        items.append({
            "code": clean(r["제공기관코드"]), "inst": clean(r["제공기관명"]),
            "category": clean(r.get("대형폐기물구분명")), "item_name": name,
            "spec": tidy(r.get("대형폐기물규격")) or SPEC_MISSING,
            "spec_blank": not clean(r.get("대형폐기물규격")),
            "fee_won": fee, "fee_type": "free" if free else "paid",
            "source": "전국대형폐기물수거수수료정보표준데이터",
            "base_date": clean(r.get("데이터기준일자")),
        })

    # 2) 성남시 별표(수준 1)
    sn_rows = read_csv(a.seongnam) + read_csv(a.misc)
    sn_used = 0
    for r in sn_rows:
        if r.get("check_status") not in OK_STATUS:
            skipped["성남시 미검수 행"] += 1
            continue
        fee_type = r["fee_type"]
        items.append({
            "code": SEONGNAM_CODE, "inst": SEONGNAM_NAME,
            "category": clean(r["category"]), "item_name": clean(r["item_name"]),
            "spec": clean(r["spec"]) or SPEC_MISSING, "spec_blank": not clean(r["spec"]),
            "fee_won": int(r["fee_won"] or 0) if fee_type != "unknown" else 0,
            "fee_type": fee_type,
            "source": "성남시 대형폐기물의 품목 및 수수료 기준(별표 1)",
            "base_date": SEONGNAM_BASE_DATE,
        })
        sn_used += 1

    # 3) 중복 처리: 완전히 같은 행만 제거, 단가가 다른 중복은 보존
    seen, unique, exact_dup = set(), [], 0
    for it in items:
        k = (it["code"], norm_key(it["item_name"]), norm_key(it["spec"]), it["fee_won"], it["fee_type"])
        if k in seen:
            exact_dup += 1
            continue
        seen.add(k)
        unique.append(it)
    price_groups = defaultdict(set)
    for it in unique:
        price_groups[(it["code"], norm_key(it["item_name"]), norm_key(it["spec"]))].add((it["fee_won"], it["fee_type"]))
    conflicts = sum(1 for v in price_groups.values() if len(v) > 1)

    # 4) 카탈로그(품목·규격 조합 중복 제거)
    catalog = {}
    for it in unique:
        key = (norm_key(it["item_name"]), norm_key(it["spec"]))
        if key not in catalog:
            catalog[key] = {"id": len(catalog) + 1, "name": it["item_name"], "spec": it["spec"],
                            "name_norm": key[0], "spec_norm": key[1],
                            "search_text": canonical(it["item_name"]) + ("" if it["spec"] == SPEC_MISSING else canonical(it["spec"]))}  # 공백 없는 정규화 문자열
        it["catalog_id"] = catalog[key]["id"]

    # 5) 지자체
    muni = {}
    for it in unique:
        m = muni.setdefault(it["code"], {"code": it["code"], "name": it["inst"], "n": 0, "blank": 0, "dates": []})
        m["n"] += 1
        m["blank"] += 1 if it["spec_blank"] else 0
        m["dates"].append(it["base_date"])

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "municipalities.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["code", "name", "support_level", "procedure_supported", "spec_missing",
                    "data_base_date", "legal_effective_date", "item_count"])
        for m in sorted(muni.values(), key=lambda x: x["code"]):
            sn = m["code"] == SEONGNAM_CODE
            w.writerow([m["code"], m["name"], "fee_and_procedure" if sn else "fee_only",
                        "true" if sn else "false", "true" if m["blank"] == m["n"] else "false",
                        max(d for d in m["dates"] if d) if any(m["dates"]) else "",
                        SEONGNAM_LEGAL_DATE if sn else "", m["n"]])
    with open(out / "item_catalog.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "name", "spec", "name_norm", "spec_norm", "search_text"])
        for c in catalog.values():
            w.writerow([c["id"], c["name"], c["spec"], c["name_norm"], c["spec_norm"], c["search_text"]])
    with open(out / "waste_items.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["municipality_code", "catalog_id", "category", "name", "spec", "fee_won", "fee_type", "source_dataset", "base_date"])
        for it in unique:
            w.writerow([it["code"], it["catalog_id"], it["category"], it["item_name"], it["spec"],
                        it["fee_won"], it["fee_type"], it["source"], it["base_date"]])

    # 6) 리포트
    blank_all = [m["name"] for m in muni.values() if m["blank"] == m["n"]]
    types = Counter(it["fee_type"] for it in unique)
    lines = [
        "# 데이터 점검 리포트 (scripts/prepare_data.py 자동 생성)",
        "",
        f"- 생성일: {date.today().isoformat()}",
        f"- 입력 행: {len(items)} (전국 {len(items) - sn_used}, 성남시 {sn_used})",
        f"- 완전 중복 제거: {exact_dup}행",
        f"- 단가가 다른 중복(품목·규격 동일, 보존): {conflicts}건",
        f"- 제외 행: {dict(skipped) or '없음'}",
        f"- 글자 사이 공백 표기를 붙인 값(예: \"냉 장 고\" -> \"냉장고\"): {TIDIED['count']}건",
        f"- 적재 행(waste_items): {len(unique)} / 지자체 {len(muni)}곳 / 카탈로그 {len(catalog)}건",
        f"- fee_type 분포: {dict(types)}",
        f"- 규격 전부 빈칸 지자체(경고 표시 대상): {len(blank_all)}곳",
        "",
        "## 규격 전부 빈칸 지자체",
        *[f"- {n}" for n in sorted(blank_all)],
        "",
        "> 규격 빈칸은 \"규격 미기재\"로 보존했고, 0원 행은 fee_type(free/exempt)으로 구분해 제외하지 않았습니다.",
    ]
    Path(a.report).parent.mkdir(parents=True, exist_ok=True)
    Path(a.report).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:12]))


if __name__ == "__main__":
    sys.exit(main())
