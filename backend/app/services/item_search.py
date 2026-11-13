"""품목 직접 검색(trigram). LLM을 사용하지 않는다(API-03).

점수 = max(전체 유사도, 단어 유사도, 부분 문자열 포함 0.9). 검색은 정규화된 카탈로그의
search_text에서 하고, 표시는 지자체 원문 품목명·규격과 단가를 쓴다.
"""
import json
from pathlib import Path
from typing import List

from sqlalchemy import text
from sqlalchemy.engine import Connection

SEARCH_SQL = text("""
SELECT wi.id AS item_id, wi.category, wi.name, wi.spec, wi.fee_won, wi.fee_type,
       GREATEST(
         similarity(c.search_text, :q),
         word_similarity(:q, c.search_text),
         CASE WHEN c.search_text ILIKE :like ESCAPE '\\' THEN 0.9 ELSE 0 END
       ) AS score
FROM waste_items wi
JOIN item_catalog c ON c.id = wi.catalog_id
WHERE wi.municipality_code = :code
  AND (c.search_text ILIKE :like ESCAPE '\\' OR c.search_text % :q OR :q <% c.search_text)
ORDER BY score DESC, wi.name, wi.spec, wi.id
LIMIT :limit
""")


def escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


_SYN_PATH = Path(__file__).resolve().parents[3] / "data" / "synonyms.json"
_SYNONYMS = {}
if _SYN_PATH.exists():
    _SYNONYMS = {k: v for k, v in json.loads(_SYN_PATH.read_text(encoding="utf-8")).items() if not k.startswith("_")}


def normalize_query(q: str) -> str:
    """정제 스크립트의 canonical()과 같은 방식: 공백 제거, 소문자, 동의어 사전 적용."""
    t = "".join(q.split()).lower()
    for variant in sorted(_SYNONYMS, key=len, reverse=True):
        t = t.replace(variant, _SYNONYMS[variant])
    return t


def search_items(conn: Connection, municipality_code: str, q: str, limit: int) -> List[dict]:
    q = normalize_query(q)
    rows = conn.execute(SEARCH_SQL, {
        "q": q, "like": "%" + escape_like(q) + "%", "code": municipality_code, "limit": limit,
    }).mappings().all()
    return [{
        "item_id": r["item_id"], "category": r["category"], "name": r["name"], "spec": r["spec"],
        "fee_won": r["fee_won"], "fee_type": r["fee_type"], "score": round(float(r["score"]), 2),
    } for r in rows]
