"""절차 RAG: 지자체 안내문 청크 검색 → LLM 정리 → 검증 → 응답.

원칙(SDD 10절):
- 근거 청크가 없으면 만들지 않는다(insufficient_evidence).
- 모든 단계·체크리스트에 존재하는 청크 id 인용이 있어야 한다. 숫자(전화번호·시간·날짜)는 인용한 청크에 있는 값만 허용한다.
- 검증 실패는 1회 재시도, 그래도 실패하거나 LLM을 쓸 수 없으면 청크 원문을 그대로 보여 준다(raw_chunks, degraded).
- 청크가 소량이라 키워드 점수로 고른다. 임베딩 검색은 청크가 늘어날 때 추가한다.
"""
import re
from typing import Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core import config
from app.services import usage
from app.services.llm import LlmUnavailable, generate_procedure

TOP_K = 5
EXCERPT_MAX = 200
KEYWORDS = ["신고", "접수", "수수료", "납부", "결제", "배출", "부착", "수거", "예약", "신고처"]
ALWAYS = ("신고절차", "신고처")
APPLIANCE_SECTION = "대형폐가전 무상 방문 수거"
NO_EVIDENCE = "해당 지자체의 안내를 확인하십시오."


def fetch_chunks(conn: Connection, code: str) -> List[dict]:
    rows = conn.execute(text("""
        SELECT id, source_name, section, content, base_date
        FROM procedure_chunks WHERE municipality_code = :c ORDER BY id"""), {"c": code}).mappings().all()
    return [dict(r) for r in rows]


def select_chunks(chunks: List[dict], has_exempt: bool, k: int = TOP_K) -> List[dict]:
    """무상수거 안내는 면제(exempt) 품목이 있을 때만 포함한다. 나머지는 키워드 점수 순."""
    pool = [c for c in chunks if c["section"] != APPLIANCE_SECTION or has_exempt]

    def score(c):
        body = (c["section"] or "") + " " + c["content"]
        return (c["section"] in ALWAYS, sum(body.count(w) for w in KEYWORDS), -c["id"])

    return sorted(pool, key=score, reverse=True)[:k]


def _citation(c: dict) -> dict:
    ex = re.sub(r"\s+", " ", c["content"]).strip()
    return {"chunk_id": c["id"], "source_name": c["source_name"], "section": c["section"],
            "base_date": c["base_date"].isoformat() if c.get("base_date") else None,
            "excerpt": ex[:EXCERPT_MAX]}


def _digits(s: str) -> set:
    """두 자리 이상 숫자 덩어리(전화번호·시간·날짜·금액)만 비교한다. 한 자리 숫자는 서수 표현 등으로 자주 쓰여 제외."""
    return set(re.findall(r"\d{2,}", s))


def validate(result: dict, selected: List[dict]) -> Optional[Tuple[List[dict], List[dict]]]:
    """통과하면 (steps, checklist), 실패하면 None."""
    by_id: Dict[int, dict] = {c["id"]: c for c in selected}
    if not isinstance(result, dict):
        return None
    steps_in, check_in = result.get("steps"), result.get("checklist") or []
    if not isinstance(steps_in, list) or not (1 <= len(steps_in) <= 8) or not isinstance(check_in, list):
        return None

    def ok_item(item, text_keys):
        if not isinstance(item, dict):
            return None
        ids = item.get("citation_ids")
        if not isinstance(ids, list) or not ids or not all(isinstance(i, int) and i in by_id for i in ids):
            return None
        texts = [item.get(k) for k in text_keys]
        if not all(isinstance(t, str) and t.strip() for t in texts):
            return None
        allowed = _digits(" ".join(by_id[i]["content"] for i in ids))
        if not _digits(" ".join(texts)) <= allowed:
            return None
        return ids, [t.strip() for t in texts]

    steps, checklist = [], []
    for n, item in enumerate(steps_in, start=1):
        r = ok_item(item, ["title", "detail"])
        if r is None:
            return None
        steps.append({"order": n, "title": r[1][0][:60], "detail": r[1][1][:300], "citation_ids": r[0]})
    for item in check_in[:5]:
        r = ok_item(item, ["text"])
        if r is None:
            return None
        checklist.append({"text": r[1][0][:200], "citation_ids": r[0]})
    return steps, checklist


def _raw(selected: List[dict], reason: str) -> dict:
    return {"procedure": {"status": "raw_chunks", "steps": [], "checklist": [],
                          "warnings": ["안내문 원문을 그대로 표시합니다. 해당 지자체의 안내를 확인하십시오."]},
            "citations": [_citation(c) for c in selected], "degraded": True, "degraded_reason": reason}


def make_procedure(chunks: List[dict], supported: bool, has_exempt: bool) -> dict:
    """반환: {"procedure", "citations", "degraded", "degraded_reason"} (DB 연결 없이 동작)."""
    if not supported:
        return {"procedure": {"status": "unsupported", "steps": [], "checklist": [],
                              "warnings": ["이 지역은 수수료만 제공합니다. 절차는 해당 지자체의 안내를 확인하십시오."]},
                "citations": [], "degraded": False, "degraded_reason": None}
    selected = select_chunks(chunks, has_exempt)
    if not any(c["section"] in ALWAYS for c in selected):
        return {"procedure": {"status": "insufficient_evidence", "steps": [], "checklist": [],
                              "warnings": ["절차 근거를 찾지 못했습니다. " + NO_EVIDENCE]},
                "citations": [], "degraded": False, "degraded_reason": None}

    notes = ["무상 방문 수거 대상 품목이 포함되어 있습니다."] if has_exempt else []
    payload = {"chunks": [{"id": c["id"], "section": c["section"], "content": c["content"]} for c in selected],
               "notes": notes}
    try:
        for _ in range(2):  # 검증 실패 시 1회 재시도
            if not usage.try_use_llm(config.settings.daily_llm_limit):
                return _raw(selected, "LLM_DAILY_LIMIT")
            checked = validate(generate_procedure(payload), selected)
            if checked:
                steps, checklist = checked
                cited = {i for it in steps + checklist for i in it["citation_ids"]}
                return {"procedure": {"status": "ok", "steps": steps, "checklist": checklist, "warnings": []},
                        "citations": [_citation(c) for c in selected if c["id"] in cited],
                        "degraded": False, "degraded_reason": None}
        return _raw(selected, "PROCEDURE_VALIDATION_FAILED")
    except LlmUnavailable:
        return _raw(selected, "LLM_UNAVAILABLE")
