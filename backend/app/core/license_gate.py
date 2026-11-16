"""공개 서비스에 노출할 지자체를 제한한다(이용허락 확인된 지자체만).

환경변수 ALLOWED_MUNICIPALITY_CODES에 지자체 코드를 쉼표로 적으면 그 지자체만 API에 노출한다.
비어 있으면 제한하지 않는다(로컬 개발·평가용). 공개 서버(Render)에서는 반드시 값을 지정한다.
예) ALLOWED_MUNICIPALITY_CODES=3780000
근거 기록은 docs/research/data_license_log.md를 따른다.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.errors import AppError


class _GateSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    allowed_municipality_codes: str = ""


def allowed_codes():
    """허용 코드 집합. 제한이 없으면 None."""
    raw = _GateSettings().allowed_municipality_codes
    codes = {c.strip() for c in raw.split(",") if c.strip()}
    return codes or None


def is_allowed(code: str) -> bool:
    allowed = allowed_codes()
    return allowed is None or code in allowed


def ensure_allowed(code: str) -> None:
    """허용되지 않은 지자체면 404로 거절한다(기존 '지원하지 않는 지자체' 오류와 같은 코드)."""
    if not is_allowed(code):
        raise AppError(404, "MUNICIPALITY_NOT_FOUND",
                       "이용 허락을 확인 중인 지자체입니다. 현재 제공하지 않습니다.")
