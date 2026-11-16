"""API-07 피드백 시험."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.core.database import get_engine
from app.main import app

client = TestClient(app)
SEONGNAM, SUWON = "3780000", "3740000"
needs_db = pytest.mark.skipif(not settings.database_url, reason="DATABASE_URL 없음")


def fb(pid, **body):
    return client.post(f"/api/v1/estimates/{pid}/feedback", json=body)


@pytest.mark.parametrize("body", [
    {},                                              # type 없음
    {"type": "unknown"},
    {"type": "other", "comment": "가" * 301},
    {"type": "other", "line_no": 0},
    {"type": "other", "line_no": 31},
    {"type": "other", "line_no": "1"},               # 문자열 정수 거부
    {"type": "wrong_item", "suggested_item_id": 0},
])
def test_검증_오류(body):
    r = fb("abcdefghij", **body)
    assert r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.fixture
def est():
    item = client.get("/api/v1/items/search", params={"municipality_code": SEONGNAM, "q": "책상", "limit": 3}).json()["items"][0]
    d = client.post("/api/v1/estimates", json={"municipality_code": SEONGNAM,
                                               "lines": [{"item_id": item["item_id"], "quantity": 1}]}).json()
    yield d["public_id"], item
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM estimates WHERE public_id = :p"), {"p": d["public_id"]})


@needs_db
def test_피드백_저장(est):
    pid, item = est
    r = fb(pid, type="wrong_item", line_no=1, comment="  규격이 다릅니다.  ", suggested_item_id=item["item_id"])
    assert r.status_code == 201 and r.json()["status"] == "received"
    with get_engine().connect() as c:
        row = c.execute(text("SELECT line_no, type, comment, suggested_item_id FROM feedback WHERE id = :i"),
                        {"i": r.json()["feedback_id"]}).mappings().one()
    assert row["line_no"] == 1 and row["type"] == "wrong_item" and row["comment"] == "규격이 다릅니다."


@needs_db
def test_전체_피드백은_줄번호_없이(est):
    assert fb(est[0], type="other").status_code == 201


@needs_db
def test_없는_줄번호는_거부(est):
    r = fb(est[0], type="other", line_no=5)
    assert r.status_code == 400 and r.json()["error"]["detail"][0]["field"] == "line_no"


@needs_db
def test_제안_품목은_품목오류에서만_그리고_같은_지자체만(est):
    pid, item = est
    assert fb(pid, type="other", suggested_item_id=item["item_id"]).status_code == 400
    other = client.get("/api/v1/items/search", params={"municipality_code": SUWON, "q": "소파", "limit": 1}).json()["items"][0]
    r = fb(pid, type="wrong_item", suggested_item_id=other["item_id"])
    assert r.status_code == 400 and r.json()["error"]["detail"][0]["field"] == "suggested_item_id"


@needs_db
def test_없는_견적과_만료_견적(est):
    assert fb("zzzzzzzzzz", type="other").status_code == 404
    with get_engine().begin() as c:
        c.execute(text("UPDATE estimates SET expires_at = now() - interval '1 day' WHERE public_id = :p"), {"p": est[0]})
    r = fb(est[0], type="other")
    assert r.status_code == 410 and r.json()["error"]["code"] == "ESTIMATE_EXPIRED"


@needs_db
def test_분당_제한(est):
    from app.core import config
    old = config.settings.rate_limit_per_minute
    config.settings.rate_limit_per_minute = 2
    try:
        codes = [fb(est[0], type="other").status_code for _ in range(3)]
        assert codes == [201, 201, 429]
    finally:
        config.settings.rate_limit_per_minute = old


@needs_db
def test_견적이_지워지면_피드백도_지워진다(est):
    pid, _ = est
    fid = fb(pid, type="other", comment="x").json()["feedback_id"]
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM estimates WHERE public_id = :p"), {"p": pid})
        assert c.execute(text("SELECT count(*) FROM feedback WHERE id = :i"), {"i": fid}).scalar() == 0
