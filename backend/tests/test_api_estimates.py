"""API-05, API-06 시험. DB가 필요한 시험은 DATABASE_URL이 없으면 건너뛴다."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.core.database import get_engine
from app.main import app

client = TestClient(app)
SEONGNAM, SUWON = "3780000", "3740000"
needs_db = pytest.mark.skipif(not settings.database_url, reason="DATABASE_URL 없음")


def body(lines, code=SEONGNAM, input_text=None):
    b = {"municipality_code": code, "lines": lines}
    if input_text is not None:
        b["input_text"] = input_text
    return b


# ---- 검증 오류(DB 불필요) ----
@pytest.mark.parametrize("payload", [
    {"municipality_code": SEONGNAM},                                              # lines 없음
    body([]),                                                                      # 빈 lines
    body([{"item_id": 1, "quantity": 0}]),                                         # 수량 0
    body([{"item_id": 1, "quantity": 100}]),                                       # 수량 100
    body([{"item_id": 1, "quantity": 1.5}]),                                       # 소수
    body([{"item_id": 1, "quantity": "2"}]),                                       # 문자열
    body([{"item_id": 1, "quantity": 1, "operator_fee_won": -1}]),                 # 음수 작업비
    body([{"item_id": "a", "quantity": 1}]),                                       # item_id 형식
    body([{"item_id": 1, "quantity": 1}] * 31),                                    # 31줄
    body([{"item_id": 1, "quantity": 1}], input_text="가" * 501),                  # 입력 501자
])
def test_견적_검증_오류(payload):
    r = client.post("/api/v1/estimates", json=payload)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# ---- DB 필요 ----
def _find(code, q):
    r = client.get("/api/v1/items/search", params={"municipality_code": code, "q": q, "limit": 20})
    return r.json()["items"]


@pytest.fixture
def created():
    ids = []
    yield ids
    if ids:
        with get_engine().begin() as conn:
            conn.execute(text("DELETE FROM estimates WHERE public_id = ANY(:p)"), {"p": ids})


@needs_db
def test_견적_생성_계산과_조회(created):
    desk = next(i for i in _find(SEONGNAM, "책상") if i["fee_type"] == "paid")
    fridge = next(i for i in _find(SEONGNAM, "냉장고") if i["fee_type"] == "exempt")
    r = client.post("/api/v1/estimates", json=body([
        {"raw_text": "책상", "item_id": desk["item_id"], "quantity": 2, "operator_fee_won": 10000},
        {"raw_text": "냉장고", "item_id": fridge["item_id"], "quantity": 1},
    ], input_text="책상 2개, 냉장고"))
    assert r.status_code == 201
    d = r.json()
    created.append(d["public_id"])
    assert len(d["public_id"]) == 10 and d["share_path"] == "/s/" + d["public_id"]
    l1, l2 = d["lines"]
    assert l1["unit_fee_won"] == desk["fee_won"] and l1["municipal_fee_won"] == desk["fee_won"] * 2
    assert l1["operator_fee_won"] == 10000
    assert l2["fee_type"] == "exempt" and l2["unit_fee_won"] == 0 and l2["municipal_fee_won"] == 0
    t = d["totals"]
    assert t["municipal_fee_total_won"] == desk["fee_won"] * 2
    assert t["operator_fee_total_won"] == 10000
    assert t["grand_total_won"] == desk["fee_won"] * 2 + 10000
    assert d["procedure"]["status"] == "insufficient_evidence"
    assert d["citations"] == [] and d["data_base_date"] == "2026-11-13"
    assert "input_text" not in d

    g = client.get("/api/v1/estimates/" + d["public_id"])
    assert g.status_code == 200
    gd = g.json()
    assert gd["lines"] == d["lines"] and gd["totals"] == d["totals"]
    assert "input_text" not in gd


@needs_db
def test_수수료만_제공_지자체는_절차_unsupported(created):
    item = _find(SUWON, "소파")[0]
    r = client.post("/api/v1/estimates", json=body([{"item_id": item["item_id"], "quantity": 1}], code=SUWON))
    assert r.status_code == 201
    created.append(r.json()["public_id"])
    assert r.json()["procedure"]["status"] == "unsupported"


@needs_db
def test_다른_지자체_품목은_거부():
    item = _find(SUWON, "소파")[0]
    r = client.post("/api/v1/estimates", json=body([{"item_id": item["item_id"], "quantity": 1}], code=SEONGNAM))
    assert r.status_code == 400 and r.json()["error"]["code"] == "ITEM_NOT_IN_MUNICIPALITY"
    r2 = client.post("/api/v1/estimates", json=body([{"item_id": 999999999, "quantity": 1}]))
    assert r2.status_code == 400 and r2.json()["error"]["code"] == "ITEM_NOT_IN_MUNICIPALITY"


@needs_db
def test_없는_지자체():
    r = client.post("/api/v1/estimates", json=body([{"item_id": 1, "quantity": 1}], code="0000000"))
    assert r.status_code == 404 and r.json()["error"]["code"] == "MUNICIPALITY_NOT_FOUND"


@needs_db
def test_없는_견적과_만료_견적(created):
    assert client.get("/api/v1/estimates/없는아이디").json()["error"]["code"] == "ESTIMATE_NOT_FOUND"
    item = _find(SEONGNAM, "책상")[0]
    d = client.post("/api/v1/estimates", json=body([{"item_id": item["item_id"], "quantity": 1}])).json()
    created.append(d["public_id"])
    with get_engine().begin() as conn:
        conn.execute(text("UPDATE estimates SET expires_at = now() - interval '1 day' WHERE public_id = :p"),
                     {"p": d["public_id"]})
    g = client.get("/api/v1/estimates/" + d["public_id"])
    assert g.status_code == 410 and g.json()["error"]["code"] == "ESTIMATE_EXPIRED"
