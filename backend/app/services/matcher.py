"""줄별 후보 검색 + (필요할 때만) LLM 선택.

- 검색 점수만으로 확실한 줄(1등 점수 ≥ 0.85, 2등과 차이 ≥ 0.15)은 LLM 없이 matched.
- 애매한 줄만 모아 LLM 1회 호출. LLM이 후보 안에서 고르면 matched, null이면 ambiguous.
- LLM 사용 불가(키 없음·실패·일일 상한)면 degraded: 검색 점수 기준으로 표시하고 자동 선택은 하지 않는다.
"""
from typing import List, Optional, Tuple

from sqlalchemy.engine import Connection

from app.core import config
from app.services import usage
from app.services.item_search import search_items
from app.services.line_parser import ParsedLine
from app.services.llm import LlmUnavailable, choose_candidates

CAND_LIMIT = 3
FETCH_LIMIT = 5
SURE_SCORE = 0.85
SURE_GAP = 0.15
SCORE_REASON = "검색 점수 기준"
SUBSTR_MAX_QUERIES = 12


def _clear_winner(cands: List[dict]) -> bool:
    if not cands or cands[0]["score"] < SURE_SCORE:
        return False
    return len(cands) == 1 or cands[0]["score"] - cands[1]["score"] >= SURE_GAP


def _search(conn: Connection, code: str, query: str) -> List[dict]:
    """전체 문구로 못 찾으면 단어별로 검색해 합친다(예: "3인용 소파" → "소파" 후보 + "3인용" 후보).
    합친 결과는 점수를 낮춰 자동 선택(matched)이 되지 않게 하고 LLM·사용자 선택으로 넘긴다."""
    found = search_items(conn, code, query, FETCH_LIMIT)
    if found:
        return found
    merged = {}

    def add(rows, cap):
        for c in rows:
            if c["item_id"] not in merged or c["score"] > merged[c["item_id"]]["score"]:
                merged[c["item_id"]] = dict(c, score=round(min(c["score"], cap), 2))

    tokens = query.split()
    if len(tokens) >= 2:
        for t in tokens:
            add(search_items(conn, code, t, FETCH_LIMIT), 0.8)
    if not merged:  # 붙여 쓴 복합어(로봇청소기, 소파베드): 긴 부분 문자열부터 찾는다
        compact = "".join(tokens)
        tried = 0
        for size in range(len(compact) - 1, 1, -1):
            # 두 글자는 단어 앞부분일 때만 쓴다("스타일러"에서 "일러"가 보일러와 겹치는 오탐을 막기 위해)
            starts = [0] if size == 2 else range(0, len(compact) - size + 1)
            for i in starts:
                if tried >= SUBSTR_MAX_QUERIES:
                    break
                tried += 1
                add(search_items(conn, code, compact[i:i + size], FETCH_LIMIT), 0.7)
            if merged:
                break
    return sorted(merged.values(), key=lambda c: -c["score"])[:FETCH_LIMIT]


def match_lines(conn: Connection, code: str, lines: List[ParsedLine]) -> Tuple[List[dict], bool, Optional[str]]:
    results = []
    pending = []  # LLM에 물어볼 줄
    for pl in lines:
        cands = _search(conn, code, pl.query) if pl.query else []
        cands = [dict(c, reason=SCORE_REASON) for c in cands]
        r = {"line_no": pl.line_no, "raw_text": pl.raw_text, "quantity": pl.quantity,
             "status": "unmatched", "needs_review": True, "selected_item_id": None,
             "candidates": cands[:CAND_LIMIT], "note": pl.note}
        if not cands:
            r["note"] = r["note"] or "일치하는 품목이 없습니다. 직접 검색하십시오."
        elif _clear_winner(cands):
            r.update(status="matched", needs_review=False, selected_item_id=cands[0]["item_id"])
        else:
            r.update(status="ambiguous", note=r["note"] or "규격 또는 품목을 선택하십시오.")
            pending.append((r, cands))
        results.append(r)

    degraded, reason = False, None
    if pending:
        settings = config.settings
        try:
            if not usage.try_use_llm(settings.daily_llm_limit):
                raise LlmUnavailable("일일 한도")
            batch = [{"line_no": r["line_no"], "text": r["raw_text"],
                      "options": [{"n": i + 1, "name": c["name"], "spec": c["spec"]}
                                  for i, c in enumerate(cands[:FETCH_LIMIT])]}
                     for r, cands in pending]
            picks = choose_candidates(batch)
            for r, cands in pending:
                p = picks.get(r["line_no"])
                n = p["n"] if p else None
                if n is not None and 1 <= n <= len(cands[:FETCH_LIMIT]):
                    chosen = cands[n - 1]
                    ordered = [dict(chosen, reason=(p["reason"] or SCORE_REASON))] + \
                              [c for c in r["candidates"] if c["item_id"] != chosen["item_id"]]
                    r.update(candidates=ordered[:CAND_LIMIT], status="matched", needs_review=False,
                             selected_item_id=chosen["item_id"], note=None)
        except LlmUnavailable as e:
            degraded = True
            reason = "LLM_UNAVAILABLE" if str(e) != "일일 한도" else "LLM_DAILY_LIMIT"
    return results, degraded, reason
