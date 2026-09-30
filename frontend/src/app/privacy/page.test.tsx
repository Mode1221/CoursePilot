import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Privacy from "./page";
import Terms from "../terms/page";

describe("법률 문서 페이지", () => {
  it("개인정보처리방침에 국외 이전(오사카)이 명시된다", () => {
    const { container } = render(<Privacy />);
    expect(container.textContent).toContain("국외 이전");
    expect(container.textContent).toContain("오사카");
  });

  it("체험 기록 삭제 기한과 카카오 로그인 수집 항목을 밝힌다", () => {
    const { container } = render(<Privacy />);
    expect(container.textContent).toContain("30일");
    expect(container.textContent).toContain("카카오 회원번호");
  });

  it("두 문서 모두 베타 적용본이며 바뀔 수 있음을 상단에 알린다", () => {
    for (const Page of [Privacy, Terms]) {
      const { container, unmount } = render(<Page />);
      const note = container.querySelector('[role="note"]');
      expect(note?.textContent).toContain("베타 기간에 적용되는 내용");
      unmount();
    }
  });

  it("국외 이전은 이전받는 자·국가·항목·거부 방법을 모두 적는다(제28조의8)", () => {
    const text = render(<Privacy />).container.textContent ?? "";
    for (const item of ["Anthropic PBC", "미국", "일본", "이전 항목", "거부할 수 있으나"]) {
      expect(text).toContain(item);
    }
  });

  it("약관은 생성형 AI 이용을 알린다(인공지능기본법 제31조)", () => {
    const { container } = render(<Terms />);
    expect(container.textContent).toContain("인공지능 이용 고지");
  });

  it("약관은 장소 정보가 실제와 다를 수 있음을 밝힌다", () => {
    const { container } = render(<Terms />);
    expect(container.textContent).toContain("방문 전 매장에 직접 확인");
  });
});
