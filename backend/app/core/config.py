from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    cors_origins: str = "http://localhost:5173"
    daily_llm_limit: int = 200
    embedding_model: str = ""  # [검증 필요] 모델명 확정 후 입력
    # 모델명은 자주 바뀌므로 환경변수로 교체할 수 있게 둔다. [검증 필요] 사용 가능 여부는 scripts/llm_smoke.py로 확인.
    gemini_model: str = "gemini-2.5-flash-lite"
    groq_model: str = "llama-3.3-70b-versatile"
    llm_timeout_seconds: int = 15
    rate_limit_per_minute: int = 10


settings = Settings()
