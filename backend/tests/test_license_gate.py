"""이용 허락 확인된 지자체만 노출하는 제한(ALLOWED_MUNICIPALITY_CODES) 시험. DB 없이 동작한다."""
import pytest
from fastapi.testclient import TestClient

from app.core import license_gate
from app.core.config import settings
from app.main import app

client = TestClient(app)
needs_db = pytest.mark.skipif(not settings.database_url, reason="DATABASE_URL 없음")


def test_환경변수가_비어_있으면_제한하지_않는다(monkeypatch):
    monkeypatch.delenv("ALLOWED_MUNICIPALITY_CODES", raising=False)
    monkeypatch.setattr(license_gate, "_GateSettings", lambda: type("S", (), {"allowed_municipality_codes": ""})())
    assert license_gate.allowed_codes() is None
    assert license_gate.is_allowed("3220000") is True


def test_쉼표_목록과_공백을_처리한다(monkeypatch):
    monkeypatch.setenv("ALLOWED_MUNICIPALITY_CODES", " 3780000 , 3330000 ,, ")
    assert license_gate.allowed_codes() == {"3780000", "3330000"}
    assert license_gate.is_allowed("3780000") is True
    assert license_gate.is_allowed("3220000") is False


@pytest.fixture()
def only_seongnam(monkeypatch):
    monkeypatch.setenv("ALLOWED_MUNICIPALITY_CODES", "3780000")


def _assert_blocked(r):
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "MUNICIPALITY_NOT_FOUND"


def test_허용되지_않은_지자체_검색은_404(only_seongnam):
    _assert_blocked(client.get("/api/v1/items/search", params={"municipality_code": "3220000", "q": "소파"}))


def test_허용되지_않은_지자체_분석은_404(only_seongnam):
    _assert_blocked(client.post("/api/v1/estimates/parse", json={"municipality_code": "3220000", "text": "소파 1개"}))


def test_허용되지_않은_지자체_질문은_404(only_seongnam):
    _assert_blocked(client.post("/api/v1/qa", json={"municipality_code": "3220000", "question": "신고는 어떻게 합니까"}))


def test_허용되지_않은_지자체_견적은_404(only_seongnam):
    _assert_blocked(client.post("/api/v1/estimates", json={
        "municipality_code": "3220000", "input_text": "소파 1개",
        "lines": [{"item_id": 1, "quantity": 1}]}))


@needs_db
def test_지자체_목록은_허용된_곳만_보인다(only_seongnam):
    items = client.get("/api/v1/municipalities").json()["items"]
    assert [i["code"] for i in items] == ["3780000"]
