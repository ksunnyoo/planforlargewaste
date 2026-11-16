"""절차 RAG 시험. LLM은 가짜 함수로 대체(conftest). 청크 선택·검증은 DB 없이도 시험한다."""
import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.core.database import get_engine
from app.main import app
from app.services import usage
from app.services.llm import LlmUnavailable, set_procedure_override
from app.services.procedure import make_procedure, select_chunks, validate

client = TestClient(app)
SEONGNAM = "3780000"
needs_db = pytest.mark.skipif(not settings.database_url, reason="DATABASE_URL 없음")

D = datetime.date(2026, 11, 13)
CHUNKS = [
    {"id": 1, "source_name": "S", "section": "신고처", "content": "전화 신고 월~금 09~18시. 인터넷 신고.", "base_date": D},
    {"id": 2, "source_name": "S", "section": "신고절차", "content": "1. 신고 2. 수수료 납부 3. 접수번호 부착 후 배출 4. 수거", "base_date": None},
    {"id": 3, "source_name": "S", "section": "대형폐가전 무상 방문 수거", "content": "예약 콜센터 1599-0903. 무상 방문 수거.", "base_date": D},
    {"id": 4, "source_name": "S", "section": "담당부서", "content": "자원순환과 031-729-4987", "base_date": D},
]


def good(payload):
    return {"steps": [{"title": "신고", "detail": "신고합니다.", "citation_ids": [2]}],
            "checklist": [{"text": "접수번호를 부착하십시오.", "citation_ids": [2]}]}


# ---- 청크 선택 ----
def test_무상수거_청크는_면제_품목이_있을_때만_포함():
    assert 3 not in [c["id"] for c in select_chunks(CHUNKS, has_exempt=False)]
    assert 3 in [c["id"] for c in select_chunks(CHUNKS, has_exempt=True)]


def test_신고절차_청크가_가장_앞():
    assert select_chunks(CHUNKS, False)[0]["section"] in ("신고절차", "신고처")


# ---- 검증 ----
def test_검증_통과():
    sel = select_chunks(CHUNKS, False)
    assert validate(good({}), sel) is not None


@pytest.mark.parametrize("bad", [
    {"steps": [{"title": "a", "detail": "b", "citation_ids": []}]},                    # 인용 없음
    {"steps": [{"title": "a", "detail": "b", "citation_ids": [999]}]},                 # 없는 청크 id
    {"steps": [{"title": "a", "detail": "b", "citation_ids": ["2"]}]},                 # id 형식 오류
    {"steps": []},                                                                     # 단계 없음
    {"steps": [{"title": "a", "detail": "", "citation_ids": [2]}]},                    # 빈 문장
    {"steps": [{"title": "a", "detail": "문의 031-111-2222", "citation_ids": [2]}]},   # 근거에 없는 숫자
    {"steps": [{"title": "a", "detail": "b", "citation_ids": [2]}], "checklist": [{"text": "x", "citation_ids": []}]},
    "문자열",
])
def test_검증_실패(bad):
    assert validate(bad, select_chunks(CHUNKS, False)) is None


def test_근거에_있는_숫자는_허용():
    r = {"steps": [{"title": "신고", "detail": "월~금 09~18시에 신고합니다.", "citation_ids": [1]}]}
    assert validate(r, select_chunks(CHUNKS, False)) is not None


# ---- make_procedure 분기 ----
def test_미지원_지자체는_unsupported():
    r = make_procedure([], False, False)
    assert r["procedure"]["status"] == "unsupported" and r["citations"] == [] and not r["degraded"]


def test_청크가_없으면_근거부족():
    r = make_procedure([], True, False)
    assert r["procedure"]["status"] == "insufficient_evidence" and r["procedure"]["steps"] == []


def test_정상이면_인용된_청크만_citations에():
    set_procedure_override(good)
    r = make_procedure(CHUNKS, True, False)
    assert r["procedure"]["status"] == "ok"
    assert [c["chunk_id"] for c in r["citations"]] == [2]
    assert r["citations"][0]["base_date"] is None and len(r["citations"][0]["excerpt"]) <= 200


def test_검증_실패는_1회_재시도_후_성공():
    calls = []

    def flaky(p):
        calls.append(1)
        return {"steps": []} if len(calls) == 1 else good(p)
    set_procedure_override(flaky)
    assert make_procedure(CHUNKS, True, False)["procedure"]["status"] == "ok" and len(calls) == 2


def test_검증_계속_실패하면_원문_표시():
    set_procedure_override(lambda p: {"steps": []})
    r = make_procedure(CHUNKS, True, False)
    assert r["procedure"]["status"] == "raw_chunks" and r["degraded"] and r["citations"]
    assert r["degraded_reason"] == "PROCEDURE_VALIDATION_FAILED"


def test_LLM_실패는_원문_표시():
    def boom(p):
        raise LlmUnavailable("x")
    set_procedure_override(boom)
    r = make_procedure(CHUNKS, True, False)
    assert r["procedure"]["status"] == "raw_chunks" and r["degraded_reason"] == "LLM_UNAVAILABLE"


def test_일일_상한_초과는_원문_표시():
    from app.core import config
    old = config.settings.daily_llm_limit
    config.settings.daily_llm_limit = 0
    try:
        r = make_procedure(CHUNKS, True, False)
        assert r["procedure"]["status"] == "raw_chunks" and r["degraded_reason"] == "LLM_DAILY_LIMIT"
    finally:
        config.settings.daily_llm_limit = old


# ---- 엔드투엔드(DB 필요, 청크 적재 필요) ----
def _chunks_loaded():
    if not settings.database_url:
        return False
    with get_engine().connect() as c:
        return c.execute(text("SELECT count(*) FROM procedure_chunks WHERE municipality_code=:c"),
                         {"c": SEONGNAM}).scalar() > 0


@pytest.fixture
def cleanup():
    ids = []
    yield ids
    if ids:
        with get_engine().begin() as conn:
            conn.execute(text("DELETE FROM estimates WHERE public_id = ANY(:p)"), {"p": ids})


@needs_db
def test_견적에_절차와_근거가_저장되고_조회된다(cleanup):
    if not _chunks_loaded():
        pytest.skip("procedure_chunks 없음: scripts/load_procedure.py 실행 필요")
    items = client.get("/api/v1/items/search", params={"municipality_code": SEONGNAM, "q": "책상", "limit": 5}).json()["items"]
    r = client.post("/api/v1/estimates", json={"municipality_code": SEONGNAM,
                                               "lines": [{"item_id": items[0]["item_id"], "quantity": 1}]})
    assert r.status_code == 201
    d = r.json()
    cleanup.append(d["public_id"])
    assert d["procedure"]["status"] == "ok" and d["degraded"] is False
    cited = {i for s in d["procedure"]["steps"] for i in s["citation_ids"]}
    assert cited <= {c["chunk_id"] for c in d["citations"]}
    assert "무상" not in " ".join(c["section"] for c in d["citations"])  # 면제 품목이 없으면 무상수거 청크 제외
    g = client.get("/api/v1/estimates/" + d["public_id"]).json()
    assert g["procedure"] == d["procedure"] and g["citations"] == d["citations"]


@needs_db
def test_LLM_실패해도_견적은_생성되고_degraded(cleanup):
    if not _chunks_loaded():
        pytest.skip("procedure_chunks 없음")

    def boom(p):
        raise LlmUnavailable("x")
    set_procedure_override(boom)
    items = client.get("/api/v1/items/search", params={"municipality_code": SEONGNAM, "q": "책상", "limit": 5}).json()["items"]
    r = client.post("/api/v1/estimates", json={"municipality_code": SEONGNAM,
                                               "lines": [{"item_id": items[0]["item_id"], "quantity": 2}]})
    d = r.json()
    cleanup.append(d["public_id"])
    assert r.status_code == 201 and d["degraded"] is True and d["degraded_reason"] == "LLM_UNAVAILABLE"
    assert d["procedure"]["status"] == "raw_chunks" and d["citations"]
    assert d["totals"]["municipal_fee_total_won"] == items[0]["fee_won"] * 2  # 금액은 영향 없음


@needs_db
def test_면제_품목이_있으면_무상수거_안내를_포함(cleanup):
    if not _chunks_loaded():
        pytest.skip("procedure_chunks 없음")
    items = client.get("/api/v1/items/search", params={"municipality_code": SEONGNAM, "q": "냉장고", "limit": 20}).json()["items"]
    ex = next(i for i in items if i["fee_type"] == "exempt")
    seen = {}

    def spy(p):
        seen["sections"] = [c["section"] for c in p["chunks"]]
        seen["notes"] = p["notes"]
        return {"steps": [{"title": "신고", "detail": "신고합니다.", "citation_ids": [p["chunks"][0]["id"]]}]}
    set_procedure_override(spy)
    r = client.post("/api/v1/estimates", json={"municipality_code": SEONGNAM,
                                               "lines": [{"item_id": ex["item_id"], "quantity": 1}]})
    cleanup.append(r.json()["public_id"])
    assert "대형폐가전 무상 방문 수거" in seen["sections"] and seen["notes"]
