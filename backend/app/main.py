from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import items, municipalities
from app.core.config import settings
from app.core.database import db_is_up
from app.core.errors import register_error_handlers

VERSION = "0.1.0"

app = FastAPI(title="대형폐기물 배출 플래너 API", version=VERSION)
register_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

v1 = APIRouter(prefix="/api/v1")
v1.include_router(municipalities.router)
v1.include_router(items.router)
app.include_router(v1)


@app.get("/health")
def health():
    """유지 호출용. DB가 내려가 있어도 200을 반환한다(04_API_SPEC API-01)."""
    db = "ok" if db_is_up() else "down"
    return {
        "status": "ok" if db == "ok" else "degraded",
        "version": VERSION,
        "db": db,
        "llm": {"primary": "unknown", "fallback": "unknown"},  # LLM 연동 후 갱신
    }
