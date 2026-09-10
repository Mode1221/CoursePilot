"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import CourseTitle from "@/components/CourseTitle";
import { Badge, Button, Input } from "@/components/ui";
import { api, ApiError } from "@/services/api";
import { saveCalendar } from "@/services/calendar";
import { shareService } from "@/services/shareService";
import { useCourseStore } from "@/store/courseStore";
import { toast } from "@/store/toastStore";
import { useUserStore } from "@/store/userStore";

const STAGE_LABELS: Record<string, string> = {
  decomposition: "조건 분석",
  search: "후보 수집",
  validation: "영업시간·이동 검증",
  relaxing: "조건 완화 재시도",
  editing: "부분 수정 반영",
  done: "마무리",
};

// 첫 사용자가 무엇을 입력할지 바로 알 수 있게 하는 예시(클릭 시 입력창에 채움)
const EXAMPLES = [
  "토요일 오후 1시 성수동, 3시간, 도보 10분 이내",
  "금요일 저녁 7시 강남역에서 출발, 회식 4명, 1인 3만원",
  "일요일 오전 11시 연남동 브런치 데이트",
  "내일 비 온대, 홍대에서 두 군데만",
];

function stageLabel(stage: string | null): string {
  return stage ? STAGE_LABELS[stage] ?? stage : "";
}

/** 오류 메시지에 추적 id 를 덧붙인다(문의 시 로그 대조용). */
function errorMessage(e: unknown, fallback: string): string {
  if (!(e instanceof ApiError)) return fallback;
  return e.requestId ? `${e.message} (오류 코드: ${e.requestId})` : e.message;
}

export default function ChatPanel({ courseId }: { courseId: string }) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmRelax, setConfirmRelax] = useState(false);
  const [completed, setCompleted] = useState(false);
  const courseCompleted = useCourseStore((s) => s.course?.completed ?? false);
  const locked = useCourseStore((s) => s.locked);
  const stage = useCourseStore((s) => s.stage);
  const messages = useCourseStore((s) => s.messages);
  const setCourse = useCourseStore((s) => s.setCourse);
  const course = useCourseStore((s) => s.course);

  const { userId, questionsLeft, load, setQuestionsLeft } = useUserStore();

  const refreshCredits = useCallback(() => {
    if (userId) api.credits(userId).then((c) => setQuestionsLeft(c.questions_left)).catch(() => {});
  }, [userId, setQuestionsLeft]);

  useEffect(() => {
    load();
  }, [load]);

  // 랜딩에서 예시로 진입한 경우(?seed=) 입력창을 미리 채워 첫 시작 마찰을 없앤다.
  useEffect(() => {
    const seed = new URLSearchParams(window.location.search).get("seed");
    if (seed) setText(seed);
  }, []);

  useEffect(() => {
    refreshCredits();
  }, [refreshCredits]);

  async function send() {
    if (!text.trim() || sending) return;
    setError(null);
    setNotice(null);
    setSending(true);
    try {
      const res = await api.generate(courseId, text, userId ?? undefined);
      setCourse(res.course);
      setText("");
      if (res.needs_confirmation) {
        setNotice("조건에 맞는 장소가 부족합니다. 조건을 완화할까요?");
        setConfirmRelax(true);
      } else {
        setConfirmRelax(false);
        if (res.relaxed) setNotice("일부 조건을 완화해 코스를 구성했습니다.");
      }
      refreshCredits();
    } catch (e) {
      setError(errorMessage(e, "요청 실패"));
    } finally {
      setSending(false);
    }
  }

  async function relaxFeedback(accepted: boolean) {
    setConfirmRelax(false);
    api.feedback(courseId, accepted ? "relax_accepted" : "relax_rejected").catch(() => {});
    if (!accepted) {
      setNotice("조건을 다시 입력해 주세요.");
      return;
    }
    setNotice("조건을 완화해 다시 찾는 중이에요…");
    setSending(true);
    try {
      const res = await api.relax(courseId, userId ?? undefined);
      setCourse(res.course);
      setNotice(
        res.needs_confirmation
          ? "완화해도 장소가 부족해요. 지역이나 시간을 바꿔 보시겠어요?"
          : "완화된 조건으로 코스를 다시 구성했어요.",
      );
    } catch (e) {
      setError(errorMessage(e, "재시도 실패"));
    } finally {
      setSending(false);
    }
  }

  async function markCompleted() {
    const res = await api.complete(courseId).catch(() => null);
    if (res) {
      setCompleted(true);
      setNotice("다녀오셨군요! 만족하셨나요?");
    } else {
      toast("기록을 저장하지 못했어요.", "error");
    }
  }

  async function rateSatisfaction(liked: boolean) {
    setCompleted(false);
    api.satisfaction(courseId, liked).catch(() => {});
    setNotice(liked ? "좋아요! 비슷한 코스를 더 추천할게요." : "아쉬웠군요. 다음엔 더 잘 맞춰볼게요.");
  }

  async function buyPoints() {
    if (!userId) return;
    // 데모: 결제 없이 5회 충전. 실서비스에선 결제 성공 후 호출.
    const res = await api.purchase(userId, 5).catch(() => null);
    if (res) {
      setQuestionsLeft(res.questions_left);
      setError(null);
      toast("질문 5회를 충전했어요.", "success");
    } else {
      toast("충전에 실패했어요. 잠시 후 다시 시도해주세요.", "error");
    }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", background: "var(--surface)" }}>
      <header
        style={{
          padding: "var(--sp-3) var(--sp-4)",
          borderBottom: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "var(--sp-2)",
        }}
      >
        <CourseTitle courseId={courseId} title={course?.title ?? "코스"} userId={userId} />
        <span style={{ display: "flex", gap: "var(--sp-2)" }}>
          {course != null && course.items.length > 0 && (
            <Button size="sm" onClick={markCompleted}>다녀왔어요</Button>
          )}
          {course != null && course.items.length > 0 && (
            <Button size="sm" onClick={() => saveCalendar(courseId)}>
              캘린더
            </Button>
          )}
          <Button
            size="sm"
            variant="primary"
            onClick={() => shareService.share(`${window.location.origin}/share/${courseId}`)}
          >
            공유
          </Button>
        </span>
      </header>

      <div
        style={{
          flex: 1,
          padding: "var(--sp-4)",
          overflow: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "var(--sp-2)",
        }}
      >
        {messages.length === 0 && (
          <div style={{ color: "var(--text-muted)", fontSize: "var(--fs-sm)" }}>
            <p style={{ marginBottom: "var(--sp-2)" }}>이렇게 입력해 보세요</p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--sp-2)" }}>
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  onClick={() => setText(ex)}
                  style={{
                    background: "var(--surface-2)",
                    color: "var(--text)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--r-full)",
                    padding: "6px 12px",
                    fontSize: "var(--fs-sm)",
                    cursor: "pointer",
                    textAlign: "left",
                  }}
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* 새 AI 답변이 도착하면 스크린리더에도 읽히도록 라이브 영역으로 둔다 */}
        <div aria-live="polite" style={{ display: "contents" }}>
        {messages.map((m, i) => (
          <div
            key={i}
            className="cp-enter"
            style={{
              alignSelf: m.role === "user" ? "flex-end" : "flex-start",
              maxWidth: "85%",
              padding: "var(--sp-2) var(--sp-3)",
              borderRadius: "var(--r-lg)",
              fontSize: "var(--fs-sm)",
              background: m.role === "user" ? "var(--brand)" : "var(--surface-2)",
              color: m.role === "user" ? "var(--brand-contrast)" : "var(--text)",
            }}
          >
            {m.text}
          </div>
        ))}
        </div>

        {locked && (
          <div
            className="cp-enter"
            role="status"
            aria-live="polite"
            style={{ display: "flex", alignItems: "center", gap: "var(--sp-2)" }}
          >
            <Badge tone="brand">AI 작업 중</Badge>
            <span style={{ fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
              {stageLabel(stage)} · 편집이 잠깁니다
            </span>
          </div>
        )}

        {notice && (
          <p
            className="cp-enter"
            role="status"
            aria-live="polite"
            style={{ color: "var(--warn)", fontSize: "var(--fs-sm)", margin: 0 }}
          >
            {notice}
          </p>
        )}

        {confirmRelax && (
          <div style={{ display: "flex", gap: "var(--sp-2)" }}>
            <Button
              size="sm"
              variant="primary"
              disabled={sending}
              onClick={() => relaxFeedback(true)}
            >
              {sending ? "다시 찾는 중…" : "완화 수락"}
            </Button>
            <Button size="sm" disabled={sending} onClick={() => relaxFeedback(false)}>
              직접 수정
            </Button>
          </div>
        )}

        {(completed || courseCompleted) && (
          <div style={{ display: "flex", gap: "var(--sp-2)" }}>
            <Button size="sm" onClick={() => rateSatisfaction(true)}>👍 만족</Button>
            <Button size="sm" onClick={() => rateSatisfaction(false)}>👎 아쉬움</Button>
          </div>
        )}

        {error && (
          <div
            className="cp-enter"
            role="alert"
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--sp-2)",
              color: "var(--danger)",
              fontSize: "var(--fs-sm)",
            }}
          >
            <span>{error}</span>
            {/* 실패해도 입력한 문장은 남아 있으니, 그대로 한 번 더 보낼 수 있게 한다 */}
            {text.trim() && (
              <Button size="sm" disabled={sending} onClick={send}>
                다시 시도
              </Button>
            )}
          </div>
        )}
      </div>

      <footer style={{ padding: "var(--sp-3) var(--sp-4)", borderTop: "1px solid var(--border)" }}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "var(--sp-2)",
            fontSize: "var(--fs-xs)",
            color: "var(--text-muted)",
            minHeight: 20,
          }}
        >
          {userId != null && questionsLeft != null && questionsLeft > 0 && (
            <span>질문 {questionsLeft}회 남음</span>
          )}
          {userId != null && questionsLeft === 0 && (
            <span style={{ color: "var(--warn)", display: "flex", alignItems: "center", gap: "var(--sp-2)" }}>
              질문 횟수를 모두 사용했어요
              <Button size="sm" variant="ghost" onClick={buyPoints}>포인트 구매</Button>
            </span>
          )}
          {userId == null && (
            <span style={{ display: "flex", alignItems: "center", gap: "var(--sp-2)" }}>
              참여자는 수동 편집만 가능합니다
              <Link href="/onboarding" style={{ color: "var(--brand-strong)", fontWeight: 600 }}>
                가입하고 AI 쓰기
              </Link>
            </span>
          )}
        </div>
        <div style={{ display: "flex", gap: "var(--sp-2)" }}>
          <Input
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder={
              userId == null ? "가입하면 AI에게 조건을 말할 수 있어요" : "예: 토요일 오후 1시 성수동, 3시간"
            }
            disabled={sending || userId == null}
            aria-label="조건 입력"
            style={{ flex: 1 }}
          />
          <Button variant="primary" onClick={send} disabled={sending || locked || userId == null}>
            {sending ? "생성 중…" : "전송"}
          </Button>
        </div>
      </footer>
    </div>
  );
}
