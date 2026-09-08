from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수 기반 설정."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://coursepilot:coursepilot@localhost:5432/coursepilot"

    # LLM 조건 분해기. 서비스 특성(짧은 자연어→구조화 도구호출, 대량·저지연)에 맞춰
    # 기본은 Anthropic Claude Haiku 4.5. 키 없으면 규칙 기반 파서로 폴백.
    llm_provider: str = "anthropic"  # anthropic | openai
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # 지도/장소 API 어댑터 (초기 구현체: Naver)
    map_provider: str = "naver"
    naver_client_id: str = ""
    naver_client_secret: str = ""

    # 리뷰 소스(요약/스코어링 1순위: Google Places). 미설정 시 Mock 폴백
    google_maps_api_key: str = ""

    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
