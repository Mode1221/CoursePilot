"""혼자 만드는 코스: 문장 속 "무엇을"을 칸(식사·카페·술·할거리)과 칸별 검색어로 바꾼다.

"연남동에서 파스타 먹고 와인바"를 한 질의("연남동 와인 파스타")로 찾으면 어느 칸에도 맞지 않는
결과가 나오고(실측: 파스타 → 우동집), 칸 순서도 사전 순서를 따라 뒤집혔다(와인바 → 저녁).
문장에 나온 **순서대로** 칸을 세우고, 칸마다 그 말로 따로 찾고, 맞는 후보가 있으면 그 칸은 그것으로만 고른다.
합의 코스(consensus.py)는 두 사람 카드로 같은 일을 하므로 여기서는 건드리지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.schemas import Place, PlanConstraints


@dataclass(frozen=True)
class Want:
    slot: str  # meal / cafe / bar / activity
    query: str  # 칸 검색어(지역 뒤에 붙는다)
    match: tuple[str, ...]  # 이 칸 후보가 요청을 만족하는지 볼 단어(카테고리·이름). 비면 칸만 맞으면 된다


# 문장에 나오는 말 → 원하는 것. 긴 말부터 본다(“와인바”가 “와인”보다 먼저).
_WANTS: dict[str, Want] = {
    # 식사
    "파스타": Want("meal", "파스타", ("파스타", "이탈리", "양식")),
    "이탈리안": Want("meal", "이탈리안", ("파스타", "이탈리", "양식")),
    "스테이크": Want("meal", "스테이크", ("스테이크", "양식", "그릴")),
    "피자": Want("meal", "피자", ("피자",)),
    "버거": Want("meal", "수제버거", ("버거", "햄버거")),
    "멕시칸": Want("meal", "멕시칸", ("멕시", "타코", "부리또")),
    "타코": Want("meal", "타코", ("멕시", "타코")),
    "초밥": Want("meal", "초밥", ("초밥", "스시", "일식")),
    "스시": Want("meal", "스시", ("초밥", "스시", "일식")),
    "오마카세": Want("meal", "오마카세", ("오마카세", "스시", "초밥", "일식")),
    "라멘": Want("meal", "라멘", ("라멘", "일식")),
    "쌀국수": Want("meal", "쌀국수", ("쌀국수", "베트남")),
    "태국": Want("meal", "태국음식", ("태국", "타이")),
    "브런치": Want("meal", "브런치", ("브런치", "양식", "카페")),
    "삼겹살": Want("meal", "삼겹살", ("삼겹", "고기", "육류", "구이")),
    "곱창": Want("meal", "곱창", ("곱창", "막창", "대창")),
    "고깃집": Want("meal", "고깃집", ("고기", "구이", "갈비", "삼겹", "육류")),
    "고기": Want("meal", "고기", ("고기", "구이", "갈비", "삼겹", "육류", "스테이크")),
    "한식": Want("meal", "한식", ("한식", "한정식", "백반", "국밥", "찌개", "갈비")),
    "일식": Want("meal", "일식", ("일식", "초밥", "스시", "라멘", "돈까스", "우동")),
    "중식": Want("meal", "중식", ("중식", "중국")),
    "양식": Want("meal", "양식", ("양식", "이탈리", "파스타", "스테이크", "레스토랑")),
    "해산물": Want("meal", "해산물", ("해산물", "해물", "회", "조개", "생선")),
    "횟집": Want("meal", "횟집", ("회", "횟집", "해산물")),
    "떡볶이": Want("meal", "떡볶이", ("떡볶이", "분식")),
    # 카페
    "디저트": Want("cafe", "디저트", ("디저트", "케이크", "베이커리", "제과", "빵", "마카롱", "티라미수")),
    "베이커리": Want("cafe", "베이커리", ("베이커리", "제과", "빵")),
    "빵집": Want("cafe", "베이커리", ("베이커리", "제과", "빵")),
    "카페": Want("cafe", "카페", ()),
    # 술
    "와인바": Want("bar", "와인바", ("와인",)),
    "와인": Want("bar", "와인바", ("와인",)),
    "칵테일": Want("bar", "칵테일바", ("칵테일", "바")),
    "이자카야": Want("bar", "이자카야", ("이자카야", "일본식주점")),
    "위스키": Want("bar", "위스키바", ("위스키", "바")),
    "맥주": Want("bar", "맥주", ("맥주", "호프", "펍", "브루")),
    "포차": Want("bar", "포차", ("포차", "포장마차", "주점")),
    "술집": Want("bar", "술집", ()),
    "2차": Want("bar", "술집", ()),
    # 할거리
    "전시": Want("activity", "전시", ("전시", "미술", "갤러리", "박물관", "뮤지엄")),
    "미술관": Want("activity", "미술관", ("미술", "전시", "갤러리")),
    "갤러리": Want("activity", "갤러리", ("갤러리", "전시", "미술")),
    "소품샵": Want("activity", "소품샵", ("소품", "편집", "잡화", "문구", "굿즈")),
    "소품": Want("activity", "소품샵", ("소품", "편집", "잡화", "문구", "굿즈")),
    "편집숍": Want("activity", "편집숍", ("편집", "소품", "의류")),
    "팝업": Want("activity", "팝업스토어", ()),
    "서점": Want("activity", "서점", ("서점", "책")),
    "한강": Want("activity", "한강공원", ("한강", "공원")),
    "한옥": Want("activity", "한옥마을", ("한옥", "고궁", "궁", "문화")),
    "고궁": Want("activity", "고궁", ("궁", "고궁", "문화재")),
    "산책": Want("activity", "공원", ("공원", "산책", "숲", "길", "한강")),
    "공원": Want("activity", "공원", ("공원",)),
    "영화": Want("activity", "영화관", ("영화", "시네마", "CGV", "메가박스", "롯데시네마")),
    "방탈출": Want("activity", "방탈출", ("방탈출",)),
    "보드게임": Want("activity", "보드게임카페", ("보드게임",)),
    "공방": Want("activity", "공방", ("공방", "원데이", "클래스")),
    "야경": Want("activity", "야경", ("전망", "야경", "공원", "타워")),
}
_ORDER = sorted(_WANTS, key=len, reverse=True)


def wants_in_order(text: str, constraints: PlanConstraints | None = None) -> list[Want]:
    """문장에 나온 순서대로. 같은 칸·같은 검색어는 한 번만, 빼 달라고 한 말은 뺀다."""
    excluded = " ".join(constraints.exclude_keywords) if constraints else ""
    found: list[tuple[int, Want]] = []
    taken: list[tuple[int, int]] = []  # 이미 쓴 글자 구간(“와인바” 안의 “와인”을 다시 잡지 않게)
    for word in _ORDER:
        start = text.find(word)
        while start != -1:
            end = start + len(word)
            if not any(s < end and start < e for s, e in taken):
                if not (excluded and word in excluded):
                    found.append((start, _WANTS[word]))
                taken.append((start, end))
            start = text.find(word, end)
    found.sort(key=lambda x: x[0])
    out: list[Want] = []
    for _, w in found:
        if any(o.slot == w.slot and o.query == w.query for o in out):
            continue
        # 같은 칸이 연달아 나오면("한옥마을 산책") 더 구체적인 앞의 것 하나로 본다
        if out and out[-1].slot == w.slot:
            continue
        out.append(w)
    return out


def apply(constraints: PlanConstraints, text: str) -> list[Want]:
    """문장 속 요청을 칸 순서·칸별 검색어·칸 초점으로 옮긴다(합의 코스가 아닐 때만 부른다)."""
    wants = wants_in_order(text, constraints)
    if not wants:
        return []
    constraints.slot_order = [w.slot for w in wants]
    constraints.slot_queries = [[w.slot, w.query] for w in wants]
    constraints.slot_focus = [[w.slot, w.query] for w in wants if w.match]
    return wants


def match_words(query: str) -> tuple[str, ...] | None:
    """칸 초점 검색어 → 만족 판정 단어. 이 모듈이 만든 초점이 아니면 None."""
    for w in _WANTS.values():
        if w.query == query and w.match:
            return w.match
    return None


def satisfies(place: Place, words: tuple[str, ...]) -> bool:
    hay = f"{place.category or ''} {place.name}"
    return any(w in hay for w in words)
