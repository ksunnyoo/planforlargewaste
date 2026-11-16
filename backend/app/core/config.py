from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    cors_origins: str = "http://localhost:5173"
    daily_llm_limit: int = 200
    embedding_model: str = "gemini-embedding-001"  # [검증 필요] 사용 가능 여부는 scripts/embedding_smoke.py로 확인
    embedding_dim: int = 768  # db/schema.sql의 vector(768)과 같아야 함
    # 품목 검색 방식: trigram(기본) / vector / hybrid. 임베딩이 적재되기 전에는 trigram만 사용한다.
    retrieval_mode: str = "trigram"
    # 모델명은 자주 바뀌므로 환경변수로 교체할 수 있게 둔다. [검증 필요] 사용 가능 여부는 scripts/llm_smoke.py로 확인.
    gemini_model: str = "gemini-3.1-flash-lite"
    groq_model: str = "openai/gpt-oss-20b"
    llm_timeout_seconds: int = 15
    rate_limit_per_minute: int = 10


settings = Settings()
