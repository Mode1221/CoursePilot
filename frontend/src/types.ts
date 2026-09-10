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
}
