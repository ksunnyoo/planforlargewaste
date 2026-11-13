from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    gemini_api_key: str = ""
    groq_api_key: str = ""
    cors_origins: str = "http://localhost:5173"
    daily_llm_limit: int = 200
    embedding_model: str = ""  # [검증 필요] 모델명 확정 후 입력


settings = Settings()
