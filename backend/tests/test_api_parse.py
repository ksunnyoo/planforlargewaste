"""API-04 입력 분석 시험. LLM은 가짜 함수로 대체한다(실제 호출 없음)."""
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services import usage
from app.services.line_parser import parse_lines
from app.services.llm import LlmUnavailable, set_llm_override

client = TestClient(app)
SEONGNAM = "3780000"
URL = "/api/v1/estimates/parse"
needs_db = pytest.mark.skipif(not settings.database_url, reason="DATABASE_URL 없음")


@pytest.fixture(autouse=True)
def _clean():
    usage.reset_for_tests()
    set_llm_override(None)
    yield
    set_llm_override(None)
    usage.reset_for_tests()


# ---- 줄 나누기·수량(DB 불필요) ----
def test_줄나누기와_수량():
    ls = parse_lines("3인용 소파, 책상, 의자 4개")
    assert [(l.query, l.quantity) for l in ls] == [("3인용 소파", 1), ("책상", 1), ("의자", 4)]


def test_한글수량_x표기_규격숫자():
    ls = parse_lines("책상 두 개\n옷장 x3\n냉장고 300ℓ 2대")
    assert [(l.query, l.quantity) for l in ls] == [("책상", 2), ("옷장", 3), ("냉장고 300ℓ", 2)]


def test_수량_상한_99():
    l = parse_lines("의자 120개")[0]
    assert l.quantity == 99 and l.note


@pytest.mark.parametrize("body", [
    {"municipality_code": SEONGNAM},
    {"municipality_code": SEONGNAM, "text": ""},
    {"municipality_code": SEONGNAM, "text": "가" * 501},
    {"text": "소파"},
])
def test_검증_오류(body):
    r = client.post(URL, json=body)
    assert r.status_code == 400 and r.json()["error"]["code"] == "VALIDATION_ERROR"


# ---- DB 필요 ----
@needs_db
def test_지자체_없음():
    r = client.post(URL, json={"municipality_code": "0000000", "text": "소파"})
    assert r.status_code == 404 and r.json()["error"]["code"] == "MUNICIPALITY_NOT_FOUND"


@needs_db
def test_줄_31개_거부():
    r = client.post(URL, json={"municipality_code": SEONGNAM, "text": "\n".join(["소파"] * 31)})
    assert r.status_code == 400


@needs_db
def test_LLM_없이도_동작하고_degraded():
    # 키가 없으면 애매한 줄은 degraded로 표시, 자동 선택은 하지 않는다.
    def boom(batch):
        raise LlmUnavailable("x")
    set_llm_override(boom)
    r = client.post(URL, json={"municipality_code": SEONGNAM, "text": "소파, 의자 4개, 없는물건abc"})
    assert r.status_code == 200
    body = r.json()
    assert [l["quantity"] for l in body["lines"]] == [1, 4, 1]
    assert body["lines"][2]["status"] == "unmatched" and body["lines"][2]["candidates"] == []
    amb = [l for l in body["lines"] if l["status"] == "ambiguous"]
    assert amb and all(l["selected_item_id"] is None and l["needs_review"] for l in amb)
    assert body["degraded"] is True and body["degraded_reason"] == "LLM_UNAVAILABLE"
    assert body["disclaimer"]


@needs_db
def test_LLM_선택은_후보_안에서만():
    seen = {}

    def fake(batch):
        seen["batch"] = batch
        # 첫 줄은 1번 선택, 둘째 줄은 후보 밖 번호(99) → 무시되어야 함
        return {b["line_no"]: {"n": 1 if i == 0 else 99, "reason": "테스트"} for i, b in enumerate(batch)}
    set_llm_override(fake)
    r = client.post(URL, json={"municipality_code": SEONGNAM, "text": "소파, 의자"})
    assert r.status_code == 200
    body = r.json()
    assert body["degraded"] is False
    ids_by_line = {l["line_no"]: {c["item_id"] for c in l["candidates"]} for l in body["lines"]}
    for l in body["lines"]:
        if l["selected_item_id"] is not None:
            assert l["selected_item_id"] in ids_by_line[l["line_no"]]
    # 후보 밖 번호를 고른 줄은 자동 선택되지 않는다
    if len(seen["batch"]) > 1:
        second = [l for l in body["lines"] if l["line_no"] == seen["batch"][1]["line_no"]][0]
        assert second["selected_item_id"] is None and second["needs_review"]


@needs_db
def test_후보에_금액은_DB값만():
    set_llm_override(lambda b: {})
    r = client.post(URL, json={"municipality_code": SEONGNAM, "text": "소파"})
    for l in r.json()["lines"]:
        for c in l["candidates"]:
            assert set(c) == {"item_id", "name", "spec", "fee_won", "fee_type", "score", "reason", "category"} or \
                   {"item_id", "fee_won", "fee_type", "reason"} <= set(c)


@needs_db
def test_분당_제한_429():
    from app.core import config
    old = config.settings.rate_limit_per_minute
    config.settings.rate_limit_per_minute = 2
    try:
        set_llm_override(lambda b: {})
        codes = [client.post(URL, json={"municipality_code": SEONGNAM, "text": "책상"}).status_code for _ in range(3)]
        assert codes == [200, 200, 429]
        r = client.post(URL, json={"municipality_code": SEONGNAM, "text": "책상"})
        assert r.json()["error"]["code"] == "RATE_LIMITED" and "retry-after" in r.headers
    finally:
        config.settings.rate_limit_per_minute = old


@needs_db
def test_일일_상한_초과시_degraded():
    from app.core import config
    old = config.settings.daily_llm_limit
    config.settings.daily_llm_limit = 0
    try:
        set_llm_override(lambda b: {1: {"n": 1, "reason": "x"}})
        r = client.post(URL, json={"municipality_code": SEONGNAM, "text": "소파"})
        body = r.json()
        if any(l["status"] == "ambiguous" for l in body["lines"]):
            assert body["degraded"] and body["degraded_reason"] == "LLM_DAILY_LIMIT"
    finally:
        config.settings.daily_llm_limit = old


@needs_db
def test_단어_순서가_달라도_후보를_찾는다():
    # 성남시 표에는 "쇼파 / 2～3인용" 형태 → "3인용 소파"는 전체 일치가 없어 단어별 검색으로 보완
    set_llm_override(lambda b: {})
    r = client.post(URL, json={"municipality_code": SEONGNAM, "text": "3인용 소파"})
    line = r.json()["lines"][0]
    assert line["candidates"], "후보가 있어야 함"
    assert line["status"] == "ambiguous" and line["selected_item_id"] is None


@needs_db
def test_침대_검색에서_받침대_품목이_앞서지_않는다():
    r = client.get("/api/v1/items/search", params={"municipality_code": SEONGNAM, "q": "침대", "limit": 5})
    names = [i["name"] for i in r.json()["items"]]
    assert names and not names[0].startswith("거실장") and "침대" in names[0]


@needs_db
@pytest.mark.parametrize("text_in,want", [("싱글 침대", "침대"), ("로봇청소기", "청소기"), ("소파베드", "쇼파")])
def test_복합어도_관련_후보를_찾는다(text_in, want):
    set_llm_override(lambda b: {})
    line = client.post(URL, json={"municipality_code": SEONGNAM, "text": text_in}).json()["lines"][0]
    assert line["candidates"], "후보가 있어야 함"
    assert want in line["candidates"][0]["name"]
    assert line["selected_item_id"] is None  # 부분 일치는 자동 선택하지 않음

