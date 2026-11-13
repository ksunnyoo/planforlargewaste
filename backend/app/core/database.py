from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection, Engine

from app.core.config import settings
from app.core.errors import AppError


@lru_cache
def get_engine() -> Engine:
    if not settings.database_url:
        raise AppError(503, "DB_UNAVAILABLE", "데이터베이스 설정이 없습니다.")
    # 무료 DB 연결 수 제한을 고려해 풀을 작게 유지한다(SDD 13절).
    return create_engine(settings.database_url, pool_pre_ping=True, pool_size=3, max_overflow=2)


def get_db():
    """요청마다 연결 1개를 열고 끝나면 반환하는 FastAPI 의존성."""
    with get_engine().connect() as conn:
        yield conn


def db_is_up() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        return True
    except Exception:
        return False
