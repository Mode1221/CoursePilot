"""코스/장소/타임라인 도메인 스키마."""
from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum

from pydantic import (
    BaseModel,
    Field,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    model_serializer,
)


class TravelMode(str, Enum):
    WALK = "walk"
    CAR = "car"
    TRANSIT = "transit"


class Place(BaseModel):
    """장소 API 어댑터가 반환하는 정규화된 장소."""

    id: str
    name: str
    category: str | None = None
    address: str | None = None
    lat: float
    lng: float
    rating: float | None = None
    price: int | None = None  # 1인 예상 비용(원). 없으면 예산 검증에서 제외
    price_estimated: bool = False  # 카테고리 기반 추정값(실제 가격이 아님)
    category_code: str | None = None  # 카카오 category_group_code (FD6/CE7/AT4/CT1 …)
    rating_count: int | None = None  # 집계 평점의 표본 수(N<30 이면 신뢰하지 않음)
    tour_listed: bool = False  # 관광·문화 공식 등재(TourAPI 등)
    fact_tags: list[str] = Field(default_factory=list)  # 주차·단체석 등 '가능' 사실 태그
    caution_tags: list[str] = Field(default_factory=list)  # '주의' 사실 태그(원문은 저장하지 않음)
    blog_mentions: int | None = None  # 블로그 검색 결과 건수 = 인지도(원문은 저장하지 않음)
    opened_on: date | None = None  # 인허가일자(LOCALDATA). 업력 스코어링용
    google_place_id: str | None = None
    business_status: str | None = None  # OPERATIONAL | CLOSED_TEMPORARILY | CLOSED_PERMANENTLY
    # Google 콘텐츠는 캐시 기한이 있다(영업시간 30일 / 평점 90일).
    last_recommended_at: datetime | None = None  # 갱신 대상(활성 집합) 판정용
    hours_checked_at: datetime | None = None
    rating_checked_at: datetime | None = None
    closed_that_day: bool = False  # 코스 날짜가 정기휴무
    hours_unverified: bool = False  # 영업시간을 확인하지 못함 → 사용자에게 "확인 필요" 표시
    open_time: time | None = None
    close_time: time | None = None
    break_start: time | None = None
    break_end: time | None = None
    # 시드로 만든 가짜 장소. 실데이터가 들어오면 이 표시로 한 번에 지운다
    # (scripts/seed_mock_places.py --clear).
    is_mock: bool = False


class Route(BaseModel):
    """A→B 이동 정보."""

    from_place_id: str
    to_place_id: str
    mode: TravelMode
    duration_min: int
    distance_m: int


class TimelineItem(BaseModel):
    """타임라인 한 칸: 장소 + 도착/출발 시각 + 다음 장소로의 이동."""

    place: Place
    arrive: time | None = None
    depart: time | None = None
    travel_to_next: Route | None = None
    # 수동 편집으로 영업시간(브레이크 포함) 밖에 놓인 자리. 자동 생성 때는 걸러지지만
    # 손으로 넣은 자리는 사용자의 선택이라 지우지 않고 표시만 한다.
    hours_conflict: bool = False
    # 합의 코스: 이 칸에 누구의 무엇이 반영됐는지(반영 이유 칩). 없으면 빈 목록.
    attributions: list[dict] = Field(default_factory=list)


class Course(BaseModel):
    """공유/저장되는 코스 상태(Single Source of Truth)."""

    id: str
    title: str = "새 코스"
    region: str | None = None
    owner_id: str | None = None  # 생성자(로그인 회원) id
    items: list[TimelineItem] = Field(default_factory=list)
    plan_date: date | None = None  # 모임 날짜(캘린더 내보내기 기준일)
    party_size: int | None = None  # 인원수(요약·공유 텍스트 표시용)
    locked: bool = False
    completed: bool = False  # "다녀왔어요" 완주 신호를 이미 받은 코스
    viewed: bool = False  # 공유 열람 신호를 이미 반영한 코스
    satisfaction: bool | None = None  # 마지막 만족도(👍=True/👎=False)
    predicted_score: float | None = None  # 생성 시 코스 목적함수 점수(#17 만족도 대조용)
    # 합의 코스 상태(상대 카드 입력·수락). None 이면 혼자 만든 코스.
    together: TogetherState | None = None


class TogetherState(BaseModel):
    """"먼저 상대에게 묻기" 모드. 링크 토큰으로 비가입 상대가 카드를 낸다."""

    token: str  # 상대 입력 링크. 입력·교체·수락만 가능(AI 명령·삭제 불가)
    request_text: str  # 시작한 사람의 한 줄 요청(합칠 때 base 조건이 된다)
    owner_name: str = "나"
    partner_name: str = "상대"
    # 참여자 이름 → 카드(예산 포함). 상대 응답으로 내보낼 땐 예산을 지운다.
    inputs: dict[str, dict] = Field(default_factory=dict)
    accepted_by: list[str] = Field(default_factory=list)  # 둘 다 있으면 확정
    conflict_note: str | None = None
    yielded: str | None = None
    # 합친 결과의 반영 이유 전부(편집 후 다시 붙이기 위해 보관) + 코스 전체 요약 줄
    attributions: list[dict] = Field(default_factory=list)
    summary: list[dict] = Field(default_factory=list)
    # 코스를 만든 뒤 누군가 카드를 고쳤다 → "다시 합치기" 안내(수락도 초기화)
    stale: bool = False

    @model_serializer(mode="wrap")
    def _public_by_default(self, handler: SerializerFunctionWrapHandler, info: SerializationInfo):
        """저장할 때(context={"storage": True})만 카드 원문·토큰을 남긴다.

        API 응답·소켓 브로드캐스트·공유 화면 등 나머지 모든 직렬화에서는 자동으로 뺀다 —
        상대의 예산과 입력 링크 토큰이 공유 링크로 새지 않게(엔드포인트마다 잊지 않도록 모델에서).
        """
        data = handler(self)
        if not (info.context or {}).get("storage"):
            data.pop("inputs", None)
            data.pop("token", None)
            data.pop("attributions", None)
            data["submitted"] = sorted(self.inputs)
        return data


class PlanConstraints(BaseModel):
    """자연어에서 분해된 조건(7-1 Decomposition 결과)."""

    region: str | None = None
    start_place: str | None = None  # 출발지("강남역에서 출발")
    start_time: time | None = None
    end_time: time | None = None
    duration_min: int | None = None
    max_travel_min: int | None = None
    travel_mode: TravelMode = TravelMode.WALK
    prefer_indoor: bool = False  # 우천 등으로 실내 위주 코스를 원하는 경우
    strict_travel_mode: bool = False  # "도보로만" 처럼 수단 고정을 요청한 경우
    budget_max: int | None = None  # 하드 제약
    party_size: int | None = None  # 인원수
    plan_date: date | None = None  # 모임 날짜("내일", "이번 주 토요일")
    stop_count: int | None = None  # 방문할 장소 개수("2차", "세 군데")
    companion: str | None = None  # 동행유형: 데이트/친구/가족/회식/혼자 (컨텍스트 신호)
    keywords: list[str] = Field(default_factory=list)  # 조용한, 비건 등 소프트 제약
    exclude_keywords: list[str] = Field(default_factory=list)  # "술집 빼고" 같은 제외 조건
    # 합의 코스: 반드시 들어가야 할 칸(두 사람의 취향), 첫 칸 고정, 칸별 검색어.
    # 한 번의 "지역 + 키워드 전부" 질의는 "홍대 고기 전시"처럼 엉뚱한 결과를 내므로 칸마다 따로 찾는다.
    required_slots: list[str] = Field(default_factory=list)
    lead_slot: str | None = None
    slot_queries: list[list[str]] = Field(default_factory=list)  # [[slot, keyword], ...]
    slot_focus: list[list[str]] = Field(default_factory=list)  # [[slot, craving], ...] 칸 주인의 취향


Course.model_rebuild()
