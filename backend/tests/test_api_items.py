"""API-02, API-03 시험. DATABASE_URL이 없으면 DB가 필요한 시험은 건너뛴다."""
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)
SEONGNAM = "3780000"
needs_db = pytest.mark.skipif(not settings.database_url, reason="DATABASE_URL 없음")


# ---- 검증 오류(DB 불필요) ----
@pytest.mark.parametrize("params", [
    {"municipality_code": SEONGNAM},                              # q 없음
    {"municipality_code": SEONGNAM, "q": ""},                     # q 빈 값
    {"municipality_code": SEONGNAM, "q": "가" * 51},              # q 51자
    {"municipality_code": SEONGNAM, "q": "소파", "limit": 21},    # limit 초과
    {"municipality_code": SEONGNAM, "q": "소파", "limit": 0},
    {"q": "소파"},                                                 # 지자체 없음
])
def test_검색_검증_오류(params):
    r = client.get("/api/v1/items/search", params=params)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# ---- DB 필요 ----
@needs_db
def test_지자체_목록():
    r = client.get("/api/v1/municipalities")
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 144
    first = items[0]
    assert first["code"] == SEONGNAM and first["support_level"] == "fee_and_procedure"
    assert first["procedure_supported"] is True and first["spec_missing"] is False
    assert first["legal_effective_date"] == "2026-10-26"
    assert sum(1 for i in items if i["spec_missing"]) == 14


@needs_db
def test_검색_성남_소파():
    r = client.get("/api/v1/items/search", params={"municipality_code": SEONGNAM, "q": "쇼파"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert items and all(set(i) >= {"item_id", "name", "spec", "fee_won", "fee_type", "score"} for i in items)
    assert "쇼파" in items[0]["name"] or "소파" in items[0]["name"]
    scores = [i["score"] for i in items]
    assert scores == sorted(scores, reverse=True)


@needs_db
def test_검색_면제_품목_표시():
    r = client.get("/api/v1/items/search", params={"municipality_code": SEONGNAM, "q": "냉장고"})
    items = r.json()["items"]
    assert items and items[0]["fee_type"] == "exempt" and items[0]["fee_won"] == 0


@needs_db
def test_검색_limit_적용():
    r = client.get("/api/v1/items/search", params={"municipality_code": SEONGNAM, "q": "의자", "limit": 3})
    assert len(r.json()["items"]) <= 3


@needs_db
def test_검색_없는_지자체():
    r = client.get("/api/v1/items/search", params={"municipality_code": "9999999", "q": "소파"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "MUNICIPALITY_NOT_FOUND"


@needs_db
def test_검색_특수문자는_문자로_취급():
    r = client.get("/api/v1/items/search", params={"municipality_code": SEONGNAM, "q": "%"})
    assert r.status_code == 200
    assert r.json()["items"] == []


@needs_db
def test_동의어_쇼파_소파_같은_결과():
    a = client.get("/api/v1/items/search", params={"municipality_code": SEONGNAM, "q": "쇼파"}).json()["items"]
    b = client.get("/api/v1/items/search", params={"municipality_code": SEONGNAM, "q": "소파"}).json()["items"]
    assert a and [i["item_id"] for i in a] == [i["item_id"] for i in b]


def test_질의_정규화():
    from app.services.item_search import normalize_query
    assert normalize_query(" 쇼 파  3인용 ") == "소파3인용"
    assert normalize_query("TV") == "tv" and normalize_query("티비") == "tv"


@needs_db
def test_철자_변형_카펫_장농_런닝머신():
    def names(code, q):
        r = client.get("/api/v1/items/search", params={"municipality_code": code, "q": q})
        return {i["name"] for i in r.json()["items"]}
    assert "카펫" in names("3740000", "카페트")      # 수원: 카펫 표기
    assert "장롱" in names(SEONGNAM, "장농")
    assert "러닝머신" in names("3220000", "런닝머신")  # 강남: 러닝머신 표기


@needs_db
def test_괄호만_있는_검색어는_빈_결과():
    r = client.get("/api/v1/items/search", params={"municipality_code": SEONGNAM, "q": "()"})
    assert r.status_code == 200 and r.json()["items"] == []
