"""'요즘 뜨는 곳' 신호 — 광고로 만들기 어려운 신호를 중심에 둔다.

설계 원칙(창업자 지적: 블로그만 보면 체험단 광고를 핫플로 뽑는다):
1. **주 신호는 사기 어려운 것**: 검색어 트렌드(사람들이 이름을 실제로 검색), 리뷰 수 증가(다녀간 흔적).
2. **블로그는 보조**: 협찬 글을 빼고 센다. 혼자서는 핫플 판정을 못 한다(다른 신호가 같이 올라야 인정).
3. **모양을 본다**: 체험단은 1~2주에 몰렸다 끊기고, 진짜 인기는 몇 주에 걸쳐 오른다 → 스파이크 감점.
4. **최근 글의 협찬 비율이 높으면 감점**.
5. 화면엔 광고로 만들기 어려운 근거만 보여준다("최근 검색량 증가", "리뷰가 꾸준히 늘고 있음").

전부 순수 함수 — 외부 호출은 adapters/, 조합은 batch/ 에서.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.reviews.sponsored import is_sponsored

# 튜닝값 — 평가 하네스(hot 지표)로 조정한다
TREND_RECENT_WEEKS = 4
TREND_BASE_WEEKS = 8
SPIKE_RATIO = 3.0  # 최근 최대 주간값이 평균의 3배 이상이고 마지막 주가 꺾였으면 스파이크
NEW_DAYS = 365
SPONSORED_CAP = 0.5  # 최근 글 절반 이상이 협찬이면 크게 감점


@dataclass
class TrendSignal:
    growth: float | None = None  # 최근 4주 평균 / 그 전 8주 평균 (1.0 = 제자리)
    spike: bool = False
    steady_rise: bool = False  # 여러 주에 걸친 꾸준한 상승
    seasonal: bool = False  # 작년 이맘때도 이만큼 올랐다 → '뜨는' 게 아니라 계절(가을 고궁·추석 등)


@dataclass
class BlogSignal:
    recent: int = 0  # 최근 30일 비협찬 글
    previous: int = 0  # 그 전 30일 비협찬 글
    sponsored_ratio: float = 0.0  # 최근 60일 글 중 협찬 비율
    sampled: int = 0

    @property
    def velocity(self) -> float | None:
        if self.recent + self.previous < 3:
            return None  # 표본이 적으면 판단하지 않는다
        return (self.recent + 1) / (self.previous + 1)


@dataclass
class Hotness:
    score: float = 0.0  # 0~1
    reasons: list[str] = field(default_factory=list)
    sponsored_ratio: float | None = None


def trend_from_series(ratios: list[float]) -> TrendSignal:
    """데이터랩 주간 비율 시계열(오래된 → 최근)에서 상승세·스파이크를 읽는다.

    비율은 요청 안에서 최댓값 100 기준 상대값이라, 같은 시계열 안의 모양만 비교한다.
    """
    s = TrendSignal()
    vals = [v for v in ratios if v is not None]
    need = TREND_RECENT_WEEKS + TREND_BASE_WEEKS
    if len(vals) < need or max(vals) <= 0:
        return s
    recent = vals[-TREND_RECENT_WEEKS:]
    base = vals[-need:-TREND_RECENT_WEEKS]
    base_mean = sum(base) / len(base)
    recent_mean = sum(recent) / len(recent)
    s.growth = (recent_mean + 1) / (base_mean + 1)
    overall_mean = sum(vals[-need:]) / need
    peak = max(recent)
    s.spike = peak >= SPIKE_RATIO * max(overall_mean, 1) and recent[-1] < peak * 0.5
    # 꾸준함: 최근 4주 중 3주 이상이 기준 평균보다 높다
    s.steady_rise = sum(v > base_mean for v in recent) >= 3 and not s.spike
    # 계절: 1년 치가 있으면 작년 같은 4주와 비교. 작년에도 지금의 70% 이상이었으면 매년 오르는 곳이다
    # (실측: 추석·가을 직전 경복궁·인왕산둘레길·전망대가 '뜨는 곳' 상위를 차지했다)
    if len(vals) >= 52 + TREND_RECENT_WEEKS:
        last_year = vals[-52 - TREND_RECENT_WEEKS : -52]
        ly_mean = sum(last_year) / len(last_year)
        if s.growth > 1.0 and ly_mean >= 0.7 * recent_mean:
            s.seasonal = True
    return s


def blog_from_items(items: list[dict], today: date) -> BlogSignal:
    """블로그 검색(날짜순) 결과에서 최근 30일·그 전 30일의 **비협찬** 글 수와 협찬 비율."""
    sig = BlogSignal()
    cut1 = today - timedelta(days=30)
    cut2 = today - timedelta(days=60)
    in_window = 0
    sponsored = 0
    for it in items:
        d = _parse_postdate(it.get("postdate"))
        if d is None or d < cut2:
            continue
        in_window += 1
        text = f"{it.get('title', '')} {it.get('description', '')}"
        if is_sponsored(text):
            sponsored += 1
            continue
        if d >= cut1:
            sig.recent += 1
        else:
            sig.previous += 1
    sig.sampled = in_window
    sig.sponsored_ratio = round(sponsored / in_window, 3) if in_window else 0.0
    return sig


# 흔한 이름: 데이터랩은 '그 단어를 검색한 전국 사람'을 센다 → "옛날순대국밥"은 이 가게가 아니라
# 순대국밥을 찾는 모두가 잡혔다(실측). 이런 이름은 동네 이름을 붙여 조회한다.
GENERIC_NAME_WORDS = (
    "커피", "카페", "식당", "국밥", "순대", "옛날", "원조", "맛집", "치킨", "피자", "분식", "김밥", "포차", "술집",
    "호프", "빵집", "베이커리", "레스토랑", "고기", "갈비", "곱창", "막창", "횟집", "초밥", "라멘", "우동", "국수",
    "냉면", "떡볶이", "칼국수", "해장국", "감자탕", "족발", "보쌈", "돈까스", "짜장", "짬뽕", "중국집", "한식", "양식",
    "일식", "주점", "이자카야", "와인", "바", "펍", "디저트", "케이크", "브런치", "하우스", "키친", "집",
)


def is_distinctive(name: str) -> bool:
    """가게 고유의 이름인가. 흔한 단어만으로 된 이름(커피커피커피·옛날순대국밥)이면 False."""
    import re

    base = re.sub(r"\s*\S*점$", "", name.strip())  # "○○ 성수점", "본점" 제거
    rest = base.replace(" ", "")
    for w in sorted(GENERIC_NAME_WORDS, key=len, reverse=True):
        rest = rest.replace(w, "")
    return len(rest) >= 2


# 고궁·산책로·전망대 같은 명소는 할거리로는 계속 추천하되 '뜨는 곳' 딱지는 붙이지 않는다(계절형)
LANDMARK_SIGNS = ("관광,명소", "고궁", "궁", "둘레길", "산책로", "전망대", "공원", "광장", "문화유산", "유적", "산성", "능")


def is_landmark(category: str | None, name: str, category_code: str | None = None) -> bool:
    if category_code == "AT4":
        return True
    hay = f"{category or ''} {name}"
    return any(w in hay for w in LANDMARK_SIGNS if len(w) >= 2) or name.endswith(("궁", "산", "능"))


def _parse_postdate(raw) -> date | None:
    if not raw or len(str(raw)) != 8:
        return None
    try:
        s = str(raw)
        return date(int(s[:4]), int(s[4:6]), int(s[6:]))
    except ValueError:
        return None


def combine(
    trend: TrendSignal | None,
    blog: BlogSignal | None,
    review_growth: float | None,
    opened_on: date | None,
    today: date,
) -> Hotness:
    """신호를 합쳐 0~1 핫플 점수와 화면용 근거를 만든다.

    - 주 신호(검색 트렌드·리뷰 증가) 중 하나 이상이 올라야 핫플로 인정한다.
    - 블로그·신상은 주 신호가 있을 때만 가산한다(광고만으로는 핫플이 될 수 없다).
    """
    h = Hotness(sponsored_ratio=blog.sponsored_ratio if blog else None)
    primary = 0.0
    if trend and trend.growth is not None and not trend.spike and not trend.seasonal:
        if trend.growth >= 1.3:
            primary += min(0.5, (trend.growth - 1.0) * 0.5)
            h.reasons.append("최근 검색량 증가")
        if trend.steady_rise:
            primary += 0.15
            if "최근 검색량 증가" not in h.reasons:
                h.reasons.append("검색량이 꾸준히 늘고 있음")
    if review_growth is not None and review_growth >= 1.15:
        primary += min(0.35, (review_growth - 1.0) * 1.0)
        h.reasons.append("리뷰가 꾸준히 늘고 있음")

    if primary <= 0:
        return h  # 주 신호 없음 → 블로그가 아무리 많아도 핫플 아님

    bonus = 0.0
    if blog and blog.velocity is not None and blog.velocity >= 1.5:
        bonus += min(0.15, (blog.velocity - 1.0) * 0.1)
    if opened_on and (today - opened_on).days <= NEW_DAYS:
        bonus += 0.1
        h.reasons.append("1년 안에 생긴 곳")
    penalty = 0.0
    if blog and blog.sampled >= 5 and blog.sponsored_ratio >= SPONSORED_CAP:
        penalty += 0.3  # 최근 글이 협찬 위주 → 캠페인 중일 가능성
    if trend and trend.spike:
        penalty += 0.2
    h.score = round(max(0.0, min(1.0, primary + bonus - penalty)), 3)
    if h.score == 0:
        h.reasons = []
    return h
