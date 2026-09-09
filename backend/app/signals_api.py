"""학습 신호 엔드포인트.

별점·재방문·완주·만족도·조회처럼 "사용자가 남기는 신호"를 받는 라우팅을 모은다.
모두 크레딧을 쓰지 않고, 같은 신호를 두 번 받아도 한 번만 반영한다(멱등).
"""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.feedback import feedback_store
from app.popularity import popularity_store
from app.ratings import rating_store
from app.schemas import Place
from app.store import store

signals_router = APIRouter(tags=["signals"])


class RatingRequest(BaseModel):
    stars: int = Field(ge=1, le=5)


@signals_router.post("/places/{place_id}/rating")
async def rate_place(
    place_id: str, req: RatingRequest, x_user_id: str | None = Header(default=None)
) -> dict:
    """장소 원탭 별점(1~5). 자체 정량 신호로 planner 스코어에 반영 (data #9).

    같은 사람이 다시 매기면 표본을 늘리지 않고 이전 점수를 대체한다
    (반복 제출로 평균을 흔들 수 없게).
    """
    from app.ratings import user_rating_store

    if x_user_id:
        previous = user_rating_store.previous(x_user_id, place_id)
        if previous == req.stars:
            avg_same = rating_store.averages([place_id]).get(place_id)
            return {"ok": True, "average": avg_same, "counted": False}
        rating_store.submit(place_id, req.stars, replaces=previous)
        user_rating_store.remember(x_user_id, place_id, req.stars)
    else:
        rating_store.submit(place_id, req.stars)
    avg = rating_store.averages([place_id]).get(place_id)
    return {"ok": True, "average": avg}


REVISIT_WEIGHT = 2  # 재방문 의사는 장소 단위 강한 긍정(또 가고 싶다)


@signals_router.post("/places/{place_id}/revisit")
async def mark_revisit(
    place_id: str, x_user_id: str | None = Header(default=None)
) -> dict:
    """재방문 의사 토글 (data #10). "또 가고 싶어요" → 장소 인기 강한 가점.

    한 사람이 한 장소에 한 번만 의미가 있는 명시 신호라, 사용자·장소 단위로
    중복을 막는다. 로그인하지 않으면 신호로 세지 않는다(반복 호출로 부풀리기 방지).
    """
    from app.revisits import revisit_store

    if not x_user_id:
        return {"ok": True, "counted": False}
    if not revisit_store.mark(x_user_id, place_id):
        return {"ok": True, "counted": False}
    popularity_store.bump(place_id, weight=REVISIT_WEIGHT)
    return {"ok": True, "counted": True}


class FeedbackRequest(BaseModel):
    kind: str = Field(min_length=1, max_length=40)
    detail: str = Field(default="", max_length=200)


@signals_router.post("/courses/{course_id}/feedback")
async def post_feedback(course_id: str, req: FeedbackRequest) -> dict:
    """사용자 피드백 기록(#15/#16). 예: 완화 수락/거부."""
    if store.get(course_id) is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
    feedback_store.log(course_id, req.kind, req.detail)
    return {"ok": True}


VIEW_WEIGHT = 0.2  # 공유 열람은 약한 완성도 대리 신호(다수 열람 → 완성도 방증)


@signals_router.post("/courses/{course_id}/view")
async def view_course(course_id: str) -> dict:
    """공유 열람 신호 (data #5). 공유 뷰가 열릴 때 코스 장소에 약한 가점.

    완성도 대리지표(열람 많을수록 잘 만든 코스일 가능성). 인증 불필요.
    """
    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
    if course.viewed:
        # 새로고침으로 열람 신호를 계속 불릴 수 없게 코스당 한 번만 반영한다
        return {"ok": True, "already": True}
    popularity_store.bump_many([it.place.id for it in course.items], weight=VIEW_WEIGHT)
    course.viewed = True
    store.save(course)
    return {"ok": True, "already": False}


@signals_router.get("/places/{place_id}/related", response_model=list[Place])
async def related_places(place_id: str, limit: int = 5) -> list[Place]:
    """함께 가요 추천 (협업 필터링). 이 장소와 자주 함께 채택된 장소들.

    데이터가 없으면 빈 목록(콜드스타트 안전). 인증 불필요.
    """
    from app.cooccurrence import cooccurrence_store
    from app.places import place_repo

    limit = max(1, min(limit, 20))
    partners = cooccurrence_store.top_partners(place_id, limit)
    resolved = place_repo.get_many([pid for pid, _ in partners])
    found = [resolved[pid] for pid, _ in partners if pid in resolved]
    if found:
        return found
    # 콜드스타트: 공동채택 이력이 없으면 근처 인기 장소로 폴백
    return _nearby_popular(place_id, limit)


NEARBY_DEGREES = 0.02  # 위경도 약 2km 이내(정렬용 근사)


def _nearby_popular(place_id: str, limit: int) -> list[Place]:
    """같은 동네의 인기 장소. 기준 장소를 모르면 빈 목록."""
    from app.places import place_repo

    known = place_repo.get_many([place_id]).get(place_id)
    if known is None:
        return []
    candidates = [
        p
        for p in place_repo.all()
        if p.id != place_id
        and abs(p.lat - known.lat) <= NEARBY_DEGREES
        and abs(p.lng - known.lng) <= NEARBY_DEGREES
    ]
    if not candidates:
        return []
    scores = popularity_store.scores([p.id for p in candidates])
    candidates.sort(key=lambda p: (-scores.get(p.id, 0.0), -(p.rating or 0.0)))
    return candidates[:limit]


COMPLETION_WEIGHT = 3  # 완주(실제 방문)는 채택/북마크보다 강한 긍정 신호


@signals_router.post("/courses/{course_id}/complete")
async def complete_course(course_id: str) -> dict:
    """완주 신호("다녀왔어요") (data #6). 실제 방문한 코스의 장소에 강한 인기 가점.

    비로그인 참여자도 누를 수 있어 인증/크레딧 불필요.
    """
    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
    place_ids = [it.place.id for it in course.items]
    if course.completed:
        # 버튼을 여러 번 눌러도 신호가 배로 쌓이지 않게 한 번만 반영한다
        return {"ok": True, "places": len(place_ids), "already": True}
    popularity_store.bump_many(place_ids, weight=COMPLETION_WEIGHT)
    feedback_store.log(course_id, "completed", detail=f"{len(place_ids)}곳")
    course.completed = True
    store.save(course)
    return {"ok": True, "places": len(place_ids), "already": False}


SATISFACTION_WEIGHT = 2  # 완료 후 만족(👍)/불만족(👎) 원탭 평가 가중


class SatisfactionRequest(BaseModel):
    liked: bool  # 👍=True / 👎=False


@signals_router.post("/courses/{course_id}/satisfaction")
async def rate_satisfaction(course_id: str, req: SatisfactionRequest) -> dict:
    """완료 후 원탭 만족도 👍/👎 (data #8). 텍스트 아님 → 광고·약관 무관.

    만족이면 코스 장소에 +가점, 불만족이면 -가점. 인증 불필요.
    """
    course = store.get(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="코스를 찾을 수 없어요")
    if course.satisfaction is req.liked:
        # 같은 평가를 반복해도 신호가 쌓이지 않게 한다
        return {"ok": True, "already": True}
    place_ids = [it.place.id for it in course.items]
    if course.satisfaction is not None:
        # 평가를 바꾼 경우: 이전 평가 효과를 먼저 되돌린다
        undo = -SATISFACTION_WEIGHT if course.satisfaction else SATISFACTION_WEIGHT
        popularity_store.bump_many(place_ids, weight=undo)
    weight = SATISFACTION_WEIGHT if req.liked else -SATISFACTION_WEIGHT
    popularity_store.bump_many(place_ids, weight=weight)
    feedback_store.log(course_id, "liked" if req.liked else "disliked")
    course.satisfaction = req.liked
    store.save(course)
    # #17: 예측 점수 vs 실제 만족도 대조 데이터 축적
    if course.predicted_score is not None:
        from app.outcome import outcome_store

        outcome_store.record(course.predicted_score, req.liked)
    return {"ok": True, "already": False}
