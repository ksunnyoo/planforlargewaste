"""API-08 절차 질문 시험. LLM은 가짜 함수(conftest 기본값: 항상 답 없음)."""
import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.core.database import get_engine
from app.main import app
from app.services.llm import LlmUnavailable, set_qa_override
from app.services.procedure import REFUSE, answer_question, select_for_question

client = TestClient(app)
SEONGNAM = "3780000"
needs_db = pytest.mark.skipif(not settings.database_url, reason="DATABASE_URL 없음")
D = datetime.date(2026, 11, 13)
CHUNKS = [
    {"id": 1, "source_name": "S", "section": "신고처", "content": "전화 신고 월~금 09~18시. 인터넷 신고 https://waste.isdc.co.kr/", "base_date": D},
    {"id": 2, "source_name": "S", "section": "신고절차", "content": "1. 신고 2. 수수료 납부: 계좌 입금, 카드 결제 3. 접수번호 부착 후 배출 4. 수거", "base_date": None},
    {"id": 3, "source_name": "S", "section": "담당부서", "content": "자원순환과 031-729-4987", "base_date": D},
]


def test_질문과_겹치는_청크만_선택():
    sel = select_for_question(CHUNKS, "전화 신고는 몇 시까지 가능한가요?")
    assert sel and sel[0]["id"] == 1


def test_무관한_질문은_근거_없음():
    assert select_for_question(CHUNKS, "오늘 날씨 어때요?") == []


def test_근거_없음이면_LLM_호출_없이_거절():
    def must_not_call(p):
        raise AssertionError("LLM을 호출하면 안 됨")
    set_qa_override(must_not_call)
    r = answer_question(CHUNKS, "오늘 날씨 어때요?")
    assert r == {"answerable": False, "answer": REFUSE, "citations": []}


def test_정상_답변은_인용과_함께():
    set_qa_override(lambda p: {"answerable": True, "answer": "월~금 09시부터 18시까지 가능합니다.", "citation_ids": [1]})
    r = answer_question(CHUNKS, "전화 신고는 몇 시까지 가능한가요?")
    assert r["answerable"] and [c["chunk_id"] for c in r["citations"]] == [1]


def test_LLM이_근거_없다고_하면_거절():
    set_qa_override(lambda p: {"answerable": False})
    r = answer_question(CHUNKS, "신고하면 며칠 만에 수거해 가나요?")
    assert r["answerable"] is False and r["answer"] == REFUSE and r["citations"] == []


@pytest.mark.parametrize("bad", [
    {"answerable": True, "answer": "가능합니다.", "citation_ids": []},
    {"answerable": True, "answer": "가능합니다.", "citation_ids": [99]},
    {"answerable": True, "answer": "", "citation_ids": [1]},
    {"answerable": True, "answer": "문의는 031-111-2222 입니다.", "citation_ids": [1]},   # 근거에 없는 번호
    {"answerable": "true", "answer": "가능합니다.", "citation_ids": [1]},
])
def test_검증_실패는_답하지_않는다(bad):
    set_qa_override(lambda p: bad)
    r = answer_question(CHUNKS, "전화 신고는 몇 시까지 가능한가요?")
    assert r["answerable"] is False and r["citations"] == []


def test_LLM_불가는_예외():
    def boom(p):
        raise LlmUnavailable("x")
    set_qa_override(boom)
    with pytest.raises(LlmUnavailable):
        answer_question(CHUNKS, "전화 신고는 몇 시까지 가능한가요?")


# ---- API (DB 필요) ----
def _loaded():
    with get_engine().connect() as c:
        return c.execute(text("SELECT count(*) FROM procedure_chunks WHERE municipality_code=:c"), {"c": SEONGNAM}).scalar() > 0


@pytest.mark.parametrize("body", [
    {"municipality_code": SEONGNAM},
    {"municipality_code": SEONGNAM, "question": ""},
    {"municipality_code": SEONGNAM, "question": "가" * 201},
    {"question": "신고"},
])
def test_검증_오류(body):
    r = client.post("/api/v1/qa", json=body)
    assert r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_ERROR"


@needs_db
def test_수수료만_제공_지자체():
    r = client.post("/api/v1/qa", json={"municipality_code": "3740000", "question": "배출 신고는 어떻게 하나요?"})
    d = r.json()
    assert r.status_code == 200 and d["answerable"] is False and d["citations"] == []
    assert "수수료만 제공" in d["answer"] and d["disclaimer"]


@needs_db
def test_없는_지자체():
    r = client.post("/api/v1/qa", json={"municipality_code": "0000000", "question": "신고"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "MUNICIPALITY_NOT_FOUND"


@needs_db
def test_성남시_답변과_거절():
    if not _loaded():
        pytest.skip("procedure_chunks 없음")
    set_qa_override(lambda p: {"answerable": True, "answer": "월~금 09시부터 18시까지 가능합니다.",
                               "citation_ids": [p["chunks"][0]["id"]]})
    r = client.post("/api/v1/qa", json={"municipality_code": SEONGNAM, "question": "전화 신고는 몇 시까지 가능한가요?"})
    d = r.json()
    assert r.status_code == 200 and d["answerable"] and d["citations"] and d["data_base_date"] == "2026-11-13"
    r2 = client.post("/api/v1/qa", json={"municipality_code": SEONGNAM, "question": "오늘 날씨 어때요?"})
    assert r2.json()["answerable"] is False and r2.json()["answer"] == REFUSE


@needs_db
def test_LLM_불가는_503():
    if not _loaded():
        pytest.skip("procedure_chunks 없음")

    def boom(p):
        raise LlmUnavailable("x")
    set_qa_override(boom)
    r = client.post("/api/v1/qa", json={"municipality_code": SEONGNAM, "question": "전화 신고는 몇 시까지 가능한가요?"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "LLM_UNAVAILABLE"
