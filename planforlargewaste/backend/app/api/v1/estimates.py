"""API-05 견적 생성, API-06 견적 조회.

- 지자체 수수료는 서버 DB 값으로만 계산한다(요청의 금액 필드는 operator_fee_won뿐).
- 견적 시점의 단가를 estimate_lines에 저장하므로 이후 데이터가 바뀌어도 조회 결과는 같다.
- 절차 안내(RAG)는 아직 연결 전이라 procedure는 임시 응답이다(아래 build_procedure 참고).
"""
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field, StrictInt
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.database import get_engine
from app.core.errors import AppError
from app.services.fee_calculator import FeeCalculationError, LineInput, calculate

router = APIRouter()

KST = timezone(timedelta(hours=9))
DISCLAIMER = "실제 수수료와 절차는 해당 지자체의 안내를 확인하십시오."
ID_CHARS = string.ascii_letters + string.digits
EXPIRE_DAYS = 30


class LineIn(BaseModel):
    raw_text: Optional[str] = Field(None, max_length=200)
    item_id: StrictInt
    quantity: StrictInt = Field(..., ge=1, le=99)
    operator_fee_won: StrictInt = Field(0, ge=0, le=100_000_000)


class EstimateIn(BaseModel):
    municipality_code: str = Field(..., min_length=1, max_length=20)
    input_text: Optional[str] = Field(None, max_length=500)
    lines: List[LineIn] = Field(..., min_length=1, max_length=30)


def new_public_id() -> str:
    return "".join(secrets.choice(ID_CHARS) for _ in range(10))


def build_procedure(procedure_supported: bool) -> dict:
    """절차 안내 응답. RAG 연결 전까지의 임시 값(작업 후속 단계에서 교체)."""
    if not procedure_supported:
        return {"status": "unsupported", "steps": [], "checklist": [],
                "warnings": ["이 지역은 수수료만 제공합니다. 절차는 해당 지자체의 안내를 확인하십시오."]}
    return {"status": "insufficient_evidence", "steps": [], "checklist": [],
            "warnings": ["절차 안내는 준비 중입니다. 해당 지자체의 안내를 확인하십시오."]}


def iso_kst(dt: datetime) -> str:
    return dt.astimezone(KST).isoformat(timespec="seconds")


def load_response(conn, estimate_id, public_id: str) -> dict:
    est = conn.execute(text("""
        SELECT e.municipality_code, e.municipal_fee_total, e.operator_fee_total, e.degraded,
               e.created_at, e.expires_at, m.data_base_date, m.procedure_supported
        FROM estimates e JOIN municipalities m ON m.code = e.municipality_code
        WHERE e.id = :id"""), {"id": estimate_id}).mappings().one()
    rows = conn.execute(text("""
        SELECT l.line_no, l.raw_text, l.item_id, l.quantity, l.unit_fee_won, l.fee_type, l.operator_fee_won,
               w.name, w.spec
        FROM estimate_lines l JOIN waste_items w ON w.id = l.item_id
        WHERE l.estimate_id = :id ORDER BY l.line_no"""), {"id": estimate_id}).mappings().all()
    lines = [{
        "line_no": r["line_no"],
        "raw_text": r["raw_text"],
        "item": {"item_id": r["item_id"], "name": r["name"], "spec": r["spec"]},
        "quantity": r["quantity"],
        "unit_fee_won": r["unit_fee_won"],
        "fee_type": r["fee_type"],
        "municipal_fee_won": r["unit_fee_won"] * r["quantity"],
        "operator_fee_won": r["operator_fee_won"],
    } for r in rows]
    municipal, operator = est["municipal_fee_total"], est["operator_fee_total"]
    return {
        "public_id": public_id,
        "municipality_code": est["municipality_code"],
        "lines": lines,
        "totals": {"municipal_fee_total_won": municipal, "operator_fee_total_won": operator,
                   "grand_total_won": municipal + operator},
        "procedure": build_procedure(est["procedure_supported"]),
        "citations": [],
        "degraded": est["degraded"],
        "degraded_reason": None,
        "data_base_date": est["data_base_date"].isoformat() if est["data_base_date"] else None,
        "disclaimer": DISCLAIMER,
        "created_at": iso_kst(est["created_at"]),
        "expires_at": iso_kst(est["expires_at"]),
        "share_path": "/s/" + public_id,
    }


@router.post("/estimates", status_code=201)
def create_estimate(body: EstimateIn):
    """API-05 견적 생성: 서버 DB 단가로 계산해 저장하고 반환한다."""
    with get_engine().begin() as conn:
        if not conn.execute(text("SELECT 1 FROM municipalities WHERE code = :c"),
                            {"c": body.municipality_code}).first():
            raise AppError(404, "MUNICIPALITY_NOT_FOUND", "지원하지 않는 지자체입니다.")

        ids = sorted({ln.item_id for ln in body.lines})
        found = {r["id"]: r for r in conn.execute(text("""
            SELECT id, fee_won, fee_type FROM waste_items
            WHERE municipality_code = :c AND id = ANY(:ids)"""),
            {"c": body.municipality_code, "ids": ids}).mappings().all()}
        bad = [{"field": "lines[%d].item_id" % i, "reason": "해당 지자체의 품목이 아닙니다."}
               for i, ln in enumerate(body.lines) if ln.item_id not in found]
        if bad:
            raise AppError(400, "ITEM_NOT_IN_MUNICIPALITY", "선택한 품목이 해당 지자체의 품목이 아닙니다.", bad)

        try:
            results, totals = calculate([
                LineInput(found[ln.item_id]["fee_won"], found[ln.item_id]["fee_type"],
                          ln.quantity, ln.operator_fee_won) for ln in body.lines])
        except FeeCalculationError as e:
            raise AppError(400, "VALIDATION_ERROR", "입력 내용을 확인하십시오.", [{"field": "lines", "reason": str(e)}])

        for _ in range(5):  # public_id 충돌 시 재시도
            public_id = new_public_id()
            try:
                with conn.begin_nested():
                    est_id = conn.execute(text("""
                        INSERT INTO estimates (public_id, municipality_code, input_text,
                            municipal_fee_total, operator_fee_total, degraded, expires_at)
                        VALUES (:pid, :code, :txt, :mt, :ot, false, now() + make_interval(days => :d))
                        RETURNING id"""),
                        {"pid": public_id, "code": body.municipality_code, "txt": body.input_text,
                         "mt": totals.municipal_fee_total_won, "ot": totals.operator_fee_total_won,
                         "d": EXPIRE_DAYS}).scalar_one()
                break
            except IntegrityError:
                continue
        else:
            raise AppError(500, "INTERNAL_ERROR", "견적을 저장하지 못했습니다. 다시 시도하십시오.")

        for no, (ln, res) in enumerate(zip(body.lines, results), start=1):
            conn.execute(text("""
                INSERT INTO estimate_lines (estimate_id, line_no, raw_text, item_id, quantity,
                                            unit_fee_won, fee_type, operator_fee_won)
                VALUES (:e, :n, :raw, :item, :q, :u, :t, :o)"""),
                {"e": est_id, "n": no, "raw": ln.raw_text, "item": ln.item_id, "q": res.quantity,
                 "u": res.unit_fee_won, "t": res.fee_type, "o": res.operator_fee_won})
        return load_response(conn, est_id, public_id)


@router.get("/estimates/{public_id}")
def get_estimate(public_id: str):
    """API-06 견적 조회(공유). 원본 입력(input_text)은 반환하지 않는다."""
    with get_engine().connect() as conn:
        row = conn.execute(text("SELECT id, expires_at, now() AS now FROM estimates WHERE public_id = :p"),
                           {"p": public_id[:40]}).mappings().first()
        if not row:
            raise AppError(404, "ESTIMATE_NOT_FOUND", "존재하지 않는 견적입니다.")
        if row["expires_at"] <= row["now"]:
            raise AppError(410, "ESTIMATE_EXPIRED", "만료된 견적입니다.")
        return load_response(conn, row["id"], public_id)
