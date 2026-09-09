"""스코어링 계수(목적함수 가중치)를 한곳에 모은다.

지금까지 계수는 코드에 흩어진 매직 넘버였고 근거는 감(感)이었다.
여기에 모아두면 (1) 무엇이 조정 가능한 값인지 드러나고
(2) `app.pipeline.calibration` 이 라벨 데이터로 오프라인 탐색할 수 있다.
"""
from __future__ import annotations

from dataclasses import dataclass, fields, replace


@dataclass(frozen=True)
class ScoreWeights:
    """장소 스코어 계수. 값이 클수록 해당 신호를 더 신뢰한다."""

    rating: float = 0.4  # 평점(자체·외부 블렌드)
    self_rating_share: float = 0.6  # 블렌드 시 자체 별점 비중
    cold_start_rating: float = 0.2  # 행동 신호 전무 시 외부 평점 추가 가중
    popularity: float = 0.25  # 채택·북마크 인기
    context_pop: float = 0.15  # 시간대 컨텍스트 인기
    keyword: float = 0.3  # 요청 키워드 매칭 비율
    budget: float = 0.2  # 예산 여유
    pref_mood: float = 0.1  # 온보딩 선언 선호
    behavior_cat: float = 0.15  # 행동 기반 카테고리 선호
    companion: float = 0.15  # 동행유형 적합
    exclude_penalty: float = 0.5  # 제외 조건 위반 감점
    outdoor_penalty: float = 0.4  # 우천 시 야외 감점
    indoor_bonus: float = 0.15  # 우천 시 실내 가점
    party: float = 0.1  # 인원수 적합

    def replace(self, **kwargs: float) -> ScoreWeights:
        return replace(self, **kwargs)

    @classmethod
    def field_names(cls) -> tuple[str, ...]:
        return tuple(f.name for f in fields(cls))


@dataclass(frozen=True)
class CourseWeights:
    """코스(타임라인) 전체 스코어 계수."""

    length: float = 1.0  # 완성도(장소 수)
    avg_rating: float = 0.5
    diversity: float = 0.3
    travel_penalty: float = 0.02  # 총 이동 시간(분)당 감점

    def replace(self, **kwargs: float) -> CourseWeights:
        return replace(self, **kwargs)

    @classmethod
    def field_names(cls) -> tuple[str, ...]:
        return tuple(f.name for f in fields(cls))


# 운영 기본값. 캘리브레이션 결과를 반영할 때 이 값을 갱신한다.
PLACE_WEIGHTS = ScoreWeights()
COURSE_WEIGHTS = CourseWeights()
