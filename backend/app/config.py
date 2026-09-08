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

    # SMS 인증 (NHN Cloud SMS). 미설정 시 개발용 폴백(코드 응답/로그 노출).
    nhn_sms_app_key: str = ""
    nhn_sms_secret_key: str = ""
    nhn_sms_sender: str = ""  # 발신번호(사전 등록 필요)

    # 결제 (포트원/아임포트 v1). 미설정 시 개발용 폴백(검증 생략).
    portone_api_key: str = ""
    portone_api_secret: str = ""
    point_price_krw: int = 1000  # 포인트 1개당 가격(결제금액 검증용)

    # 다중 인스턴스 확장: 설정 시 Socket.IO 가 Redis pub/sub 로 인스턴스 간 브로드캐스트.
    # 미설정이면 단일 프로세스 메모리 매니저(개발/소규모 운영 기본값).
    redis_url: str = ""

    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def multi_instance(self) -> bool:
        return bool(self.redis_url)

    @property
    def sms_enabled(self) -> bool:
        return bool(self.nhn_sms_app_key and self.nhn_sms_secret_key and self.nhn_sms_sender)

    @property
    def payment_enabled(self) -> bool:
        return bool(self.portone_api_key and self.portone_api_secret)


settings = Settings()
