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

  it("두 문서 모두 법률 검토 전 초안임을 상단에 알린다", () => {
    for (const Page of [Privacy, Terms]) {
      const { container, unmount } = render(<Page />);
      const note = container.querySelector('[role="note"]');
      expect(note?.textContent).toContain("법률 검토 전 초안");
      unmount();
    }
  });

  it("약관은 장소 정보가 실제와 다를 수 있음을 밝힌다", () => {
    const { container } = render(<Terms />);
    expect(container.textContent).toContain("방문 전 반드시 해당 매장에 확인");
  });
});
