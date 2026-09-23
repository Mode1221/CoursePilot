// 백엔드 schemas.py 와 대응되는 프론트 타입

export type TravelMode = "walk" | "car" | "transit";

export const MODE_LABEL: Record<TravelMode, string> = {
  walk: "도보",
  car: "차량",
  transit: "대중교통",
};

export interface Place {
  id: string;
  name: string;
  category?: string | null;
  address?: string | null;
  lat: number;
  lng: number;
  rating?: number | null;
  price?: number | null;
  price_estimated?: boolean | null; // 카테고리 기반 추정값
  open_time?: string | null;
  close_time?: string | null;
  break_start?: string | null;
  break_end?: string | null;
  hours_unverified?: boolean | null; // 영업시간을 외부에서 확인하지 못함
  hours_checked_at?: string | null; // 영업시간을 마지막으로 확인한 시각(ISO)
  fact_tags?: string[] | null; // 주차·단체석 등 '가능' 사실 태그
  caution_tags?: string[] | null; // '주의' 사실 태그
  rating_count?: number | null; // 집계 평점의 표본 수
  opened_on?: string | null; // 인허가일자(업력 표시용)
  hot_score?: number | null; // 요즘 뜨는 정도(0~1, 광고만으로는 0)
  hot_reasons?: string[] | null; // "최근 검색량 증가" 등 — 광고로 만들기 어려운 근거
  is_popup?: boolean | null; // 기간 한정 팝업·전시
  active_until?: string | null; // 진행 종료(추정 포함)
  event_url?: string | null;
}

export interface Route {
  from_place_id: string;
  to_place_id: string;
  mode: TravelMode;
  duration_min: number;
  distance_m: number;
}

export interface TimelineItem {
  place: Place;
  arrive?: string | null;
  depart?: string | null;
  travel_to_next?: Route | null;
  /** 손으로 넣은 자리가 영업시간(브레이크 포함) 밖일 때 true. */
  hours_conflict?: boolean;
  /** 합의 코스: 이 칸에 누구의 무엇이 반영됐는지(반영 이유 칩). */
  attributions?: Attribution[];
}

/** 반영 이유 한 조각 — "👤지은 피곤해 → 이동 10분 이내". */
export interface Attribution {
  who: string;
  what: string;
  effect: string;
  slot?: string | null;
}

/** 합의 코스 상태(상대에게 나가는 형태 — 카드 원문·토큰 없음). */
export interface TogetherPublic {
  owner_name: string;
  partner_name: string;
  submitted: string[];
  accepted_by: string[];
  conflict_note?: string | null;
  yielded?: string | null;
  request_text: string;
  /** 코스 전체에 해당하는 이유 + 맞는 곳을 못 찾은 취향(솔직하게). 타임라인 위 한 줄. */
  summary?: Attribution[];
  /** 코스를 만든 뒤 카드가 바뀌어 다시 합쳐야 함 */
  stale?: boolean;
}

export interface Course {
  id: string;
  title: string;
  region?: string | null;
  plan_date?: string | null; // YYYY-MM-DD (모임 날짜)
  party_size?: number | null;
  items: TimelineItem[];
  locked: boolean;
  completed?: boolean; // "다녀왔어요" 를 이미 누른 코스
  together?: TogetherPublic | null;
}
