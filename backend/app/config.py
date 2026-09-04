from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수 기반 설정."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://coursepilot:coursepilot@localhost:5432/coursepilot"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # 지도/장소 API 어댑터 (초기 구현체: Naver)
    map_provider: str = "naver"
    naver_client_id: str = ""
    naver_client_secret: str = ""

    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
