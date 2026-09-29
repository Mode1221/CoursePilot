// 메신저 미리보기(OG) 문구. 카카오톡·스레드·인스타 DM 에 링크를 붙였을 때 보이는 제목·설명·이미지 글자.
//
// 링크를 가진 사람이 화면에서 이미 볼 수 있는 것만 쓴다 — 초대 링크는 보낸 사람 이름과 요청 한 줄,
// 공유 코스는 코스 이름·지역·날짜·장소 이름. 카드 답·예산·전화번호 같은 건 서버가 애초에 주지 않는다.
import { formatPlanDate } from "@/services/courseDate";
import { summarize } from "@/services/courseSummary";
import type { Course } from "@/types";

export const SITE_NAME = "픽앤어스";
export const DEFAULT_TITLE = "픽앤어스 — 둘이 같이 정하는 데이트 코스";
export const DEFAULT_DESCRIPTION =
  "데이트 계획, 검색 말고 상대에게 먼저 물어보세요. 30초면 둘 다 괜찮은 코스가 나옵니다.";

/** 백엔드 `GET /together/{token}/preview` 응답. */
export interface TogetherPreview {
  owner_name: string;
  request_text: string;
  built: boolean;
  region?: string | null;
  stops?: number;
}

/** 미리보기 이미지 한 장의 글자들. */
export interface OgCard {
  eyebrow: string;
  headline: string;
  sub?: string;
  chips?: string[];
}

export interface OgText {
  title: string;
  description: string;
  card: OgCard;
}

// 이미지 글꼴(public/fonts/og-sans-kr-bold.woff)에 있는 글자만 쓴다: ASCII, 한글 자모(ㄱ-ㅣ), 몇몇 기호,
// 그리고 KS X 1001 한글 2,350자(자주 쓰는 음절). 글꼴에 없는 글자는 렌더러(next/og)가 구글 글꼴을
// 내려받아 채우려 한다 — 네트워크가 막힌 서버에서는 이미지가 늦거나 두부(□)가 된다.
// 기호·이모지는 빼도 뜻이 남지만, 드문 한글 음절(예: "똠", "뷁")을 빼면 이름이 틀려지므로
// 그런 글자가 있는 문구는 통째로 쓰지 않는다(빈 문자열 → 부르는 쪽이 일반 문구로 바꾼다).
const UNSUPPORTED = /[^ -~가-힣ㄱ-ㅣ·…→←—–‘’“”•★♥♡]/gu;
const SYLLABLE = /[가-힣]/gu;

let ksHangul: Set<string> | null = null;

/** KS X 1001 완성형 한글 2,350자 = EUC-KR 0xB0A1–0xC8FE. 글꼴 부분집합과 같은 범위다. */
export function ksx1001Hangul(): Set<string> {
  if (ksHangul) return ksHangul;
  const set = new Set<string>();
  try {
    const decoder = new TextDecoder("euc-kr");
    for (let lead = 0xb0; lead <= 0xc8; lead++) {
      for (let trail = 0xa1; trail <= 0xfe; trail++) {
        set.add(decoder.decode(new Uint8Array([lead, trail])));
      }
    }
  } catch {
    /* 디코더가 없는 런타임이면 빈 집합 — 한글 문구는 일반 카드로 간다 */
  }
  ksHangul = set;
  return set;
}

export function ogSafe(text: string | null | undefined, max = 60): string {
  const cleaned = (text ?? "").replace(UNSUPPORTED, "").replace(/\s+/g, " ").trim();
  const common = ksx1001Hangul();
  if ((cleaned.match(SYLLABLE) ?? []).some((ch) => !common.has(ch))) return "";
  return cleaned.length > max ? `${cleaned.slice(0, max - 1).trimEnd()}…` : cleaned;
}

function clip(text: string, max: number): string {
  const t = text.replace(/\s+/g, " ").trim();
  return t.length > max ? `${t.slice(0, max - 1).trimEnd()}…` : t;
}

export const DEFAULT_CARD: OgCard = {
  eyebrow: "둘이 같이 정하는 데이트 코스",
  headline: "검색 말고, 상대에게 먼저 물어보세요",
  sub: "30초 카드에 답하면 둘 다 괜찮은 코스가 나와요",
};

const INVITE_FALLBACK: OgText = {
  title: "같이 데이트 코스 정하기 — 픽앤어스",
  description: "30초 카드에 답하면 둘 다 괜찮은 코스가 나와요. 가입 없음.",
  card: {
    eyebrow: "같이 정하기 · 30초 · 가입 없음",
    headline: "데이트 코스를 같이 정하자고 해요",
    sub: "탭 몇 번이면 둘 다 괜찮은 코스가 나와요",
  },
};

// 이름을 안 적고 시작하면 서버 기본값이 "나"다(together_api.py) — 받는 사람에게 "나님이"로 보이면 어색하다
const UNNAMED_OWNER = "나";

function inviteHeadline(owner: string): string {
  return owner && owner !== UNNAMED_OWNER
    ? `${owner}님이 데이트 코스를 같이 정하자고 해요`
    : "데이트 코스를 같이 정하자는 초대가 왔어요";
}

/** 같이 정하기 초대 링크. 토큰이 틀렸거나 서버가 안 되면 일반 초대 카드. */
export function inviteText(p: TogetherPreview | null): OgText {
  if (!p) return INVITE_FALLBACK;
  const owner = clip(p.owner_name || "", 12);
  const request = clip(p.request_text || "", 80);
  const title = inviteHeadline(owner);
  const where = [p.region, p.stops ? `${p.stops}곳` : null].filter(Boolean).join(" · ");
  const description = p.built
    ? `둘의 답을 합친 코스가 준비됐어요${where ? ` (${where})` : ""}. 링크에서 바로 보고 고칠 수 있어요.`
    : `${request ? `${request} — ` : ""}컨디션·땡기는 것·싫은 것만 탭하면 둘 다 괜찮은 코스가 나와요. 가입 없음.`;
  const cardOwner = ogSafe(owner, 12);
  return {
    title,
    description,
    card: {
      eyebrow: p.built ? "같이 정한 코스 · 준비 완료" : "같이 정하기 · 30초 · 가입 없음",
      headline: inviteHeadline(cardOwner),
      sub: ogSafe(p.request_text, 40) || undefined,
    },
  };
}

const COURSE_FALLBACK: OgText = {
  title: "공유된 코스 — 픽앤어스",
  description: DEFAULT_DESCRIPTION,
  card: { eyebrow: "공유된 데이트 코스", headline: "둘이 같이 정한 데이트 코스", sub: DEFAULT_CARD.sub },
};

/** 완성된 코스(읽기 전용 공유 화면). 없으면 일반 카드. */
export function courseText(course: Course | null): OgText {
  if (!course) return COURSE_FALLBACK;
  const names = course.items.map((it) => ogSafe(it.place.name, 14)).filter(Boolean);
  const day = formatPlanDate(course.plan_date);
  const eyebrow = [day, ogSafe(course.region, 16), names.length ? `${names.length}곳` : null]
    .filter(Boolean)
    .join(" · ");
  return {
    title: `${course.title} — ${SITE_NAME}`,
    description: summarize(course),
    card: {
      eyebrow: eyebrow || "공유된 데이트 코스",
      headline: ogSafe(course.title, 40) || "데이트 코스",
      chips: names.slice(0, 4),
      sub: names.length > 4 ? `외 ${names.length - 4}곳` : names.length ? undefined : "아직 장소가 없는 코스예요",
    },
  };
}
