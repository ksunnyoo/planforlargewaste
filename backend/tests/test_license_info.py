"""지자체별 이용 조건 표시 시험. DB 없이 동작하는 부분과 DB가 필요한 부분을 나눈다."""
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.license_info import CONFIRMED, RESTRICTED, UNVERIFIED, get_license, known_codes
from app.main import app

client = TestClient(app)
needs_db = pytest.mark.skipif(not settings.database_url, reason="DATABASE_URL 없음")


def test_성남은_확인됨():
    lic = get_license("3780000")
    assert lic["status"] == CONFIRMED and lic["kogl_type"] == 1
    assert lic["checked_at"] == "2026-11-16"


def test_강남은_상업적_이용_제한():
    lic = get_license("3220000")
    assert lic["status"] == RESTRICTED and lic["kogl_type"] == 4
    assert "영업 목적" in lic["summary"]


def test_해운대는_불일치로_제한_취급():
    assert get_license("3330000")["status"] == RESTRICTED


def test_수성_수원은_미확인():
    assert get_license("3460000")["status"] == UNVERIFIED
    assert get_license("3740000")["status"] == UNVERIFIED


def test_모르는_지자체는_확인_중_기본값():
    lic = get_license("9999999")
    assert lic["status"] == UNVERIFIED and lic["kogl_type"] is None
    assert "참고용" in lic["summary"]


def test_기본값을_바꿔도_원본은_변하지_않는다():
    a = get_license("3780000")
    a["status"] = "x"
    assert get_license("3780000")["status"] == CONFIRMED


def test_확인한_지자체는_5곳():
    assert known_codes() == {"3780000", "3220000", "3330000", "3460000", "3740000"}


@needs_db
def test_지자체_목록에_이용_조건이_포함된다():
    items = client.get("/api/v1/municipalities").json()["items"]
    by = {i["code"]: i for i in items}
    assert by["3780000"]["license"]["status"] == "confirmed"
    assert by["3220000"]["license"]["status"] == "restricted"
    assert all("license" in i for i in items)
