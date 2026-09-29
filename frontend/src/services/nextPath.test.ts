import { describe, expect, it } from "vitest";

import { safeNext } from "./nextPath";

describe("safeNext", () => {
  it("사이트 안 경로만 돌려준다", () => {
    expect(safeNext("/plan/abc?x=1")).toBe("/plan/abc?x=1");
    expect(safeNext("//evil.com")).toBe("/");
    expect(safeNext("/\\evil.com")).toBe("/");
    expect(safeNext("https://evil.com")).toBe("/");
    expect(safeNext(null, "/mypage")).toBe("/mypage");
    expect(safeNext("/\t/evil.com")).toBe("/");
    expect(safeNext("/\n/evil.com")).toBe("/");
    expect(safeNext("/%2F%2Fevil.com")).toBe("/%2F%2Fevil.com"); // 인코딩된 채로는 경로일 뿐
  });
});
