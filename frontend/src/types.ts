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
  open_time?: string | null;
  close_time?: string | null;
  break_start?: string | null;
  break_end?: string | null;
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
}

export interface Course {
  id: string;
  title: string;
  region?: string | null;
  items: TimelineItem[];
  locked: boolean;
}
