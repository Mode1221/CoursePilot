import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Onboarding from "./page";
import { api } from "@/services/api";
import { useUserStore } from "@/store/userStore";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("@/services/api", () => ({
  api: {
    signup: vi.fn(),
    setPreferences: vi.fn(),
    getPreferences: vi.fn(),
    requestSmsCode: vi.fn(),
    verifySmsCode: vi.fn(),
  },
  ApiError: class extends Error {
    constructor(public status: number) {
      super("api error");
    }
  },
}));

describe("온보딩", () => {
  beforeEach(() => {
    push.mockReset();
    vi.mocked(api.signup).mockReset();
    vi.mocked(api.setPreferences).mockReset();
    vi.mocked(api.getPreferences).mockResolvedValue({
      mood: null,
      region: null,
      transport: null,
      budget: null,
      diet: [],
      must_haves: [],
    });
    vi.mocked(api.requestSmsCode).mockReset();
    vi.mocked(api.verifySmsCode).mockReset();
    vi.mocked(api.requestSmsCode).mockResolvedValue({ sent: true, dev_code: "123456" });
    vi.mocked(api.verifySmsCode).mockResolvedValue({ verified: true });
    useUserStore.setState({ userId: null });
    localStorage.clear();
  });
  afterEach(cleanup);

  it("잘못된 번호는 가입 요청을 보내지 않는다", async () => {
    render(<Onboarding />);
    fireEvent.change(screen.getByPlaceholderText("010-0000-0000"), { target: { value: "123" } });
    fireEvent.click(screen.getByText("저장"));

    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    expect(api.signup).not.toHaveBeenCalled();
  });

  async function verifyPhone(phone = "010-1234-5678") {
    fireEvent.change(screen.getByPlaceholderText("010-0000-0000"), { target: { value: phone } });
    fireEvent.click(screen.getByText("인증번호 받기"));
    await waitFor(() => expect(api.requestSmsCode).toHaveBeenCalledWith(phone));
    fireEvent.click(await screen.findByText("확인"));
    await screen.findByText("휴대폰 인증 완료");
  }

  it("인증 전에는 가입하지 않는다", async () => {
    render(<Onboarding />);
    fireEvent.change(screen.getByPlaceholderText("010-0000-0000"), {
      target: { value: "010-1234-5678" },
    });
    fireEvent.click(screen.getByText("저장"));

    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    expect(api.signup).not.toHaveBeenCalled();
  });

  it("가입 후 선호를 저장하고 홈으로 이동한다", async () => {
    vi.mocked(api.signup).mockResolvedValue({ user_id: "u1", credits_left: 5 });
    vi.mocked(api.setPreferences).mockResolvedValue(undefined);

    render(<Onboarding />);
    await verifyPhone();
    fireEvent.change(screen.getByPlaceholderText("예: 성수동"), { target: { value: "성수동" } });
    fireEvent.click(screen.getByText("저장"));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
    expect(api.signup).toHaveBeenCalledWith("010-1234-5678");
    expect(api.setPreferences).toHaveBeenCalledWith(
      "u1",
      expect.objectContaining({ region: "성수동" }),
    );
  });

  it("기존 선호가 있으면 폼에 채워진다", async () => {
    useUserStore.setState({ userId: "u9" });
    vi.mocked(api.getPreferences).mockResolvedValue({
      mood: "활기찬",
      region: "연남동",
      transport: "차량",
      budget: "4~6만원",
      diet: ["채식"],
      must_haves: [],
    });

    render(<Onboarding />);

    await waitFor(() =>
      expect((screen.getByLabelText("자주 가는 지역") as HTMLInputElement).value).toBe("연남동"),
    );
    expect((screen.getByLabelText("1인 예산대") as HTMLSelectElement).value).toBe("4~6만원");
    expect((screen.getByLabelText("채식") as HTMLInputElement).checked).toBe(true);
    useUserStore.setState({ userId: null });
  });

  it("예산·제외 조건까지 5문항을 저장한다", async () => {
    vi.mocked(api.signup).mockResolvedValue({ user_id: "u1", credits_left: 5 });
    vi.mocked(api.setPreferences).mockResolvedValue(undefined);

    render(<Onboarding />);
    await verifyPhone();
    fireEvent.change(screen.getByPlaceholderText("예: 성수동"), { target: { value: "성수동" } });
    fireEvent.change(screen.getByLabelText("분위기"), { target: { value: "조용한" } });
    fireEvent.change(screen.getByLabelText("이동수단"), { target: { value: "차량" } });
    fireEvent.change(screen.getByLabelText("1인 예산대"), { target: { value: "2~4만원" } });
    fireEvent.click(screen.getByLabelText("비건"));
    fireEvent.click(screen.getByText("저장"));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
    expect(api.setPreferences).toHaveBeenCalledWith("u1", {
      mood: "조용한",
      region: "성수동",
      transport: "차량",
      budget: "2~4만원",
      diet: ["비건"],
      must_haves: [],
    });
  });

  it("항상 필요한 것을 저장한다", async () => {
    vi.mocked(api.signup).mockResolvedValue({ user_id: "u1", credits_left: 5 });
    vi.mocked(api.setPreferences).mockResolvedValue(undefined);

    render(<Onboarding />);
    await verifyPhone();
    fireEvent.click(screen.getByLabelText("주차"));
    fireEvent.click(screen.getByText("저장"));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
    expect(api.setPreferences).toHaveBeenCalledWith(
      "u1",
      expect.objectContaining({ must_haves: ["주차"] }),
    );
  });

  it("체크박스를 다시 누르면 제외 조건이 빠진다", async () => {
    vi.mocked(api.signup).mockResolvedValue({ user_id: "u1", credits_left: 5 });
    vi.mocked(api.setPreferences).mockResolvedValue(undefined);

    render(<Onboarding />);
    await verifyPhone();
    fireEvent.click(screen.getByLabelText("노키즈"));
    fireEvent.click(screen.getByLabelText("노키즈"));
    fireEvent.click(screen.getByText("저장"));

    await waitFor(() => expect(push).toHaveBeenCalledWith("/"));
    expect(api.setPreferences).toHaveBeenCalledWith(
      "u1",
      expect.objectContaining({ diet: [] }),
    );
  });

  it("실패하면 오류를 보여주고 다시 시도할 수 있다", async () => {
    vi.mocked(api.signup).mockRejectedValue(new Error("boom"));
    render(<Onboarding />);
    await verifyPhone("01012345678");
    fireEvent.click(screen.getByText("저장"));

    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
    expect(push).not.toHaveBeenCalled();
    expect(screen.getByText("저장")).toBeTruthy(); // 버튼이 다시 활성 상태
  });
});
