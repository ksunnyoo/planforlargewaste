from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(title="대형폐기물 배출 플래너 API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    """유지 호출용. DB가 내려가 있어도 200을 반환한다(04_API_SPEC API-01)."""
    return {"status": "ok", "db": "unchecked"}
