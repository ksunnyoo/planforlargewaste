"""품목 직접 검색(trigram). LLM을 사용하지 않는다(API-03).

점수 = max(전체 유사도, 단어 유사도, 부분 문자열 포함 0.9). 검색은 정규화된 카탈로그의
search_text에서 하고, 표시는 지자체 원문 품목명·규격과 단가를 쓴다.
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core import config
from app.services import embeddings

SEARCH_SQL = text("""
SELECT wi.id AS item_id, wi.category, wi.name, wi.spec, wi.fee_won, wi.fee_type,
       GREATEST(
         similarity(c.search_text, :q),
         word_similarity(:q, c.search_text),
         CASE WHEN c.name_norm LIKE :prefix ESCAPE '\\' THEN 0.95
              WHEN c.search_text ILIKE :like ESCAPE '\\' THEN 0.9 - LEAST(strpos(c.search_text, :q), 40) * 0.002
              ELSE 0 END
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
    """정제 스크립트의 canonical()과 같은 방식: 공백·괄호·구두점 제거, 소문자, 동의어 사전 적용."""
    t = re.sub(r"[\s()\[\]·,./]+", "", q).lower()
    for variant in sorted(_SYNONYMS, key=len, reverse=True):
        t = t.replace(variant, _SYNONYMS[variant])
    return t


def search_items(conn: Connection, municipality_code: str, q: str, limit: int) -> List[dict]:
    q = normalize_query(q)
    if not q:
        return []
    rows = conn.execute(SEARCH_SQL, {
        "q": q, "like": "%" + escape_like(q) + "%", "prefix": escape_like(q) + "%", "code": municipality_code, "limit": limit,
    }).mappings().all()
    return [{
        "item_id": r["item_id"], "category": r["category"], "name": r["name"], "spec": r["spec"],
        "fee_won": r["fee_won"], "fee_type": r["fee_type"], "score": round(float(r["score"]), 2),
    } for r in rows]


# ---------------- 벡터·하이브리드 검색 (C1·C2) ----------------
VECTOR_SQL = text("""
SELECT wi.id AS item_id, wi.category, wi.name, wi.spec, wi.fee_won, wi.fee_type,
       1 - (c.embedding <=> CAST(:vec AS vector)) AS cosine
FROM waste_items wi
JOIN item_catalog c ON c.id = wi.catalog_id
WHERE wi.municipality_code = :code AND c.embedding IS NOT NULL
ORDER BY c.embedding <=> CAST(:vec AS vector), wi.id
LIMIT :limit
""")

# 질의 임베딩이 실패해 trigram으로 대신한 횟수. 평가(eval)가 이 값을 읽어 벡터 검색이 실제로 쓰였는지 확인한다.
EMBED_FALLBACKS = {"count": 0}

VECTOR_ONLY_CAP = 0.7  # 벡터로만 찾은 후보는 점수를 낮춰 자동 확정(matched)이 되지 않게 한다
RRF_K = 60


def vector_search(conn: Connection, municipality_code: str, q: str, limit: int) -> List[dict]:
    """질의 임베딩이 실패하면 EmbeddingUnavailable을 낸다."""
    qn = normalize_query(q)
    if not qn:
        return []
    vec = embeddings.embed_query(qn)
    rows = conn.execute(VECTOR_SQL, {"vec": embeddings.to_pgvector(vec), "code": municipality_code, "limit": limit}).mappings().all()
    return [{"item_id": r["item_id"], "category": r["category"], "name": r["name"], "spec": r["spec"],
             "fee_won": r["fee_won"], "fee_type": r["fee_type"],
             "score": round(min(max(float(r["cosine"]), 0.0), VECTOR_ONLY_CAP), 2)} for r in rows]


def rrf_fuse(lexical: List[dict], semantic: List[dict], limit: int, k: int = RRF_K) -> List[dict]:
    """순위 기반 결합(RRF). 표시 점수는 trigram 점수를 우선하고, 벡터로만 찾은 후보는 상한을 둔다."""
    fused: Dict[int, dict] = {}
    rrf: Dict[int, float] = {}
    for rows in (lexical, semantic):
        for rank, c in enumerate(rows, start=1):
            rrf[c["item_id"]] = rrf.get(c["item_id"], 0.0) + 1.0 / (k + rank)
            if c["item_id"] not in fused or (rows is lexical):
                fused[c["item_id"]] = c
    order = sorted(fused, key=lambda i: (-rrf[i], i))
    return [fused[i] for i in order[:limit]]


def search_items_mode(conn: Connection, municipality_code: str, q: str, limit: int, mode: Optional[str] = None) -> List[dict]:
    """mode: trigram | vector | hybrid. 임베딩을 쓸 수 없으면 trigram으로 저하 동작한다."""
    mode = mode or config.settings.retrieval_mode
    if mode == "trigram":
        return search_items(conn, municipality_code, q, limit)
    try:
        sem = vector_search(conn, municipality_code, q, limit)
    except embeddings.EmbeddingUnavailable:
        EMBED_FALLBACKS["count"] += 1
        return search_items(conn, municipality_code, q, limit)
    if mode == "vector":
        return sem[:limit]
    return rrf_fuse(search_items(conn, municipality_code, q, limit), sem, limit)
