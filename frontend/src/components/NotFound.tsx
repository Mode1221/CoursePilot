import { Button } from "@/components/ui";

// 코스 없음(404) 공통 빈 상태.
export default function NotFound({ message }: { message: string }) {
  return (
    <main style={{ padding: "var(--sp-12) var(--sp-4)", maxWidth: 560, margin: "0 auto", textAlign: "center" }}>
      <h1>코스를 찾을 수 없어요</h1>
      <p style={{ color: "var(--text-muted)" }}>{message}</p>
      <a href="/" style={{ textDecoration: "none" }}>
        <Button variant="primary">새 코스 시작하기</Button>
      </a>
    </main>
  );
}
