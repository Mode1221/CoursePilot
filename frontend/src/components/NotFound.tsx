// 코스 없음(404) 공통 빈 상태.
export default function NotFound({ message }: { message: string }) {
  return (
    <main style={{ padding: 48, maxWidth: 640, margin: "0 auto" }}>
      <h1>코스를 찾을 수 없습니다</h1>
      <p style={{ color: "#888" }}>{message}</p>
      <a href="/">새 코스 시작하기</a>
    </main>
  );
}
