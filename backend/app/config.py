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

    # 경로(네이버 클라우드 플랫폼 Maps). 개발자센터 키와 별개이므로 분리해서 받는다.
    # 미설정이면 개발자센터 키로 폴백하지만, 운영에서는 반드시 NCP 키를 넣어야 한다.
    ncp_api_key_id: str = ""
    ncp_api_key: str = ""

    # 관광·문화시설 정보(공공데이터포털 TourAPI). 미설정 시 미사용.
    tourapi_service_key: str = ""

    # 장소 발견 주 원천: 카카오 로컬 REST API(무료). 미설정 시 네이버/Mock 폴백.
    kakao_rest_api_key: str = ""

    # 폐업·업력 원천: LOCALDATA(지방행정 인허가) CSV 디렉터리.
    # 무료·무인증이며 시군구 단위 파일을 주 1회 갱신한다. 비우면 필터 미적용.
    localdata_csv_dir: str = ""
    # 주 1회 내려받을 LOCALDATA CSV URL 목록(무인증 공개 파일).
    localdata_csv_urls: list[str] = []

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

    # IP 당 분당 요청 상한. E2E·부하 테스트에서는 올려 잡는다(운영 기본 60).
    rate_limit_per_min: int = 60

    # 세션 토큰 서명 키. 설정하면 사용자 id 헤더만으로는 인증되지 않는다.
    # 비워두면 개발 편의를 위해 헤더를 믿으므로, 배포 시에는 반드시 설정한다.
    session_secret: str = ""

    # 관리 엔드포인트(/admin/*) 보호. 설정 시 X-Admin-Token 헤더가 일치해야 한다.
    # 비워두면 개발 편의를 위해 열려 있으므로, 배포 시에는 반드시 설정한다.
    admin_token: str = ""

    # 임계 알림 외부 발송(슬랙/디스코드 등 웹훅 URL). 미설정 시 로그만 남긴다.
    alert_webhook_url: str = ""

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
