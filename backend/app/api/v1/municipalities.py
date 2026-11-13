from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.core.database import get_db

router = APIRouter()

LIST_SQL = text("""
SELECT code, name, support_level, procedure_supported, spec_missing,
       data_base_date, legal_effective_date, item_count
FROM municipalities
ORDER BY (support_level = 'fee_and_procedure') DESC, name
""")


@router.get("/municipalities")
def list_municipalities(conn: Connection = Depends(get_db)):
    """API-02 지원 지자체 목록. 수수료 데이터가 없는 지자체는 목록에 없다(미지원)."""
    items = []
    for r in conn.execute(LIST_SQL).mappings():
        items.append({
            "code": r["code"], "name": r["name"], "support_level": r["support_level"],
            "procedure_supported": r["procedure_supported"], "spec_missing": r["spec_missing"],
            "data_base_date": r["data_base_date"].isoformat() if r["data_base_date"] else None,
            "legal_effective_date": r["legal_effective_date"].isoformat() if r["legal_effective_date"] else None,
            "item_count": r["item_count"],
        })
    return {"items": items}
