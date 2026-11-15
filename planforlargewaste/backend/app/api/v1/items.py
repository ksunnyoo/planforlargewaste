from fastapi import APIRouter, Query
from sqlalchemy import text

from app.core.database import get_engine
from app.core.errors import AppError
from app.services.item_search import search_items

router = APIRouter()


@router.get("/items/search")
def search(
    municipality_code: str = Query(..., min_length=1, max_length=20),
    q: str = Query(..., min_length=1, max_length=50),
    limit: int = Query(10, ge=1, le=20),
):
    """API-03 품목 직접 검색(trigram, LLM 미사용)."""
    query = q.strip()
    if not query:
        raise AppError(400, "VALIDATION_ERROR", "입력 내용을 확인하십시오.",
                       [{"field": "q", "reason": "검색어를 입력하십시오."}])
    # 검증을 먼저 끝낸 뒤에 DB 연결을 연다(검증 오류는 DB 없이도 400으로 응답).
    with get_engine().connect() as conn:
        exists = conn.execute(text("SELECT 1 FROM municipalities WHERE code = :c"),
                              {"c": municipality_code}).first()
        if not exists:
            raise AppError(404, "MUNICIPALITY_NOT_FOUND", "지원하지 않는 지자체입니다.")
        return {"items": search_items(conn, municipality_code, query, limit)}
