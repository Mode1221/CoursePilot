import { describe, expect, it } from "vitest";

import type { Course } from "@/types";

import { DEFAULT_CARD, courseText, inviteText, ksx1001Hangul, ogSafe } from "./ogText";

const place = (name: string) => ({ place: { id: name, name, lat: 37.5, lng: 127 } });

describe("미리보기 문구", () => {
  it("초대 링크는 보낸 사람 이름과 요청 한 줄로", () => {
    const t = inviteText({ owner_name: "민수", request_text: "토요일 3시 성수", built: false });
    expect(t.title).toBe("민수님이 데이트 코스를 같이 정하자고 해요");
    expect(t.description).toMatch(/^토요일 3시 성수 — .*가입 없음\.$/);
    expect(t.card.headline).toBe(t.title);
    expect(t.card.sub).toBe("토요일 3시 성수");
  });

  it("이름 없이 시작한 초대(서버 기본값 \"나\")는 이름을 빼고 말한다", () => {
    const t = inviteText({ owner_name: "나", request_text: "", built: false });
    expect(t.title).toBe("데이트 코스를 같이 정하자는 초대가 왔어요");
    expect(t.card.headline).toBe(t.title);
  });

  it("합친 코스가 있으면 준비됐다고 말한다", () => {
    const t = inviteText({ owner_name: "민수", request_text: "x", built: true, region: "성수동", stops: 4 });
    expect(t.description).toMatch(/준비됐어요 \(성수동 · 4곳\)/);
    expect(t.card.eyebrow).toMatch(/준비 완료/);
  });

  it("토큰이 틀리거나 서버가 안 되면 일반 초대 카드", () => {
    const t = inviteText(null);
    expect(t.title).toBe("같이 데이트 코스 정하기 — 픽앤어스");
    expect(t.card.headline).not.toMatch(/님이/);
  });

  it("이미지에는 글꼴에 없는 글자(이모지)를 빼고 길면 자른다", () => {
    expect(ogSafe("지은✨ 🍰")).toBe("지은");
    expect(ogSafe("가".repeat(80), 10)).toBe(`${"가".repeat(9)}…`);
    expect(inviteText({ owner_name: "🙂", request_text: "", built: false }).card.headline).toBe("데이트 코스를 같이 정하자는 초대가 왔어요");
  });

  it("공유 코스는 이름·지역·장소 순서", () => {
    const course = {
      id: "c1",
      title: "성수 데이트",
      region: "성수동",
      plan_date: "2026-10-03",
      items: ["카페", "전시", "식당", "바", "공원"].map(place),
      locked: false,
    } as unknown as Course;
    const t = courseText(course);
    expect(t.title).toBe("성수 데이트 — 픽앤어스");
    expect(t.card.eyebrow).toBe("10월 3일 (토) · 성수동 · 5곳");
    expect(t.card.chips).toEqual(["카페", "전시", "식당", "바"]);
    expect(t.card.sub).toBe("외 1곳");
    expect(courseText(null).title).toBe("공유된 코스 — 픽앤어스");
  });

  it("글꼴에 없는 드문 한글이 있으면 그 문구를 쓰지 않고 일반 문구로 바꾼다", () => {
    expect(ksx1001Hangul().size).toBe(2350);
    expect(ogSafe("똥카페")).toBe("똥카페");
    expect(ogSafe("똠얌꿍")).toBe(""); // "똠" 은 KS X 1001 밖
    expect(inviteText({ owner_name: "뷁", request_text: "", built: false }).card.headline).toBe("데이트 코스를 같이 정하자는 초대가 왔어요");
    const course = { id: "c", title: "똠얌 코스", region: null, items: [], locked: false } as unknown as Course;
    expect(courseText(course).card.headline).toBe("데이트 코스");
    expect(courseText(course).title).toBe("똠얌 코스 — 픽앤어스"); // 글자 제목은 그대로(이미지만 바꾼다)
  });

  it("고정 문구는 모두 글꼴 안의 글자로만 되어 있다", () => {
    const unnamed = inviteText({ owner_name: "나", request_text: "", built: false }).card;
    const cards = [DEFAULT_CARD, inviteText(null).card, courseText(null).card, unnamed];
    for (const card of cards) {
      for (const text of [card.eyebrow, card.headline, card.sub ?? ""]) {
        expect(ogSafe(text, 200)).toBe(text);
      }
    }
    expect(ogSafe("둘이 같이 정하는 데이트 코스")).toBe("둘이 같이 정하는 데이트 코스");
  });
});
