"""관리 대시보드 HTML.

지표는 이미 모으고 있었지만 JSON 으로만 볼 수 있어서, 운영 중에 무엇이
나빠졌는지 보려면 curl 로 파싱해야 했다. 한 화면에 폴백률·유료 API 잔여
한도·학습 신호를 띄워 눈으로 확인할 수 있게 한다.

의존성 없이 한 파일에 담는다(빌드 파이프라인을 늘리지 않는다).
"""
from __future__ import annotations

DASHBOARD_HTML = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>CoursePilot 운영 대시보드</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: #fbfbfa; --fg: #1a1a19; --muted: #6b6b68; --line: #e4e4e1;
    --card: #fff; --ok: #1a7f4b; --warn: #b45309; --bad: #b91c1c;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#151514; --fg:#eeeeec; --muted:#a0a09c; --line:#2f2f2d; --card:#1e1e1c; }
  }
  * { box-sizing: border-box; }
  body { margin:0; padding:24px; background:var(--bg); color:var(--fg);
         font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
  h1 { font-size:20px; margin:0 0 4px; }
  p.sub { color:var(--muted); margin:0 0 20px; }
  .row { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:20px; }
  input, button { font:inherit; padding:8px 12px; border:1px solid var(--line);
                  border-radius:8px; background:var(--card); color:var(--fg); }
  button { cursor:pointer; }
  .grid { display:grid; gap:16px; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); }
  section { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px; }
  h2 { font-size:13px; text-transform:uppercase; letter-spacing:.04em;
       color:var(--muted); margin:0 0 12px; }
  table { width:100%; border-collapse:collapse; }
  th, td { text-align:left; padding:6px 4px; border-bottom:1px solid var(--line); }
  th { color:var(--muted); font-weight:500; }
  td.num { text-align:right; font-variant-numeric:tabular-nums; }
  .ok { color:var(--ok); } .warn { color:var(--warn); } .bad { color:var(--bad); }
  .bar { height:6px; border-radius:3px; background:var(--line); overflow:hidden; }
  .bar > span { display:block; height:100%; background:var(--ok); }
  .bar.warn > span { background:var(--warn); } .bar.bad > span { background:var(--bad); }
  .empty { color:var(--muted); }
  #error { color:var(--bad); margin-bottom:12px; }
</style>
</head>
<body>
<h1>CoursePilot 운영 대시보드</h1>
<p class="sub">폴백률·유료 API 잔여 한도·학습 신호를 한 화면에서 봅니다. 30초마다 갱신.</p>
<div class="row">
  <input id="token" type="password" placeholder="ADMIN_TOKEN (설정된 경우)" />
  <button id="refresh">새로고침</button>
</div>
<div id="error"></div>
<div class="grid">
  <section><h2>요청</h2><div id="requests"></div></section>
  <section><h2>유료 API 이번 달 사용량</h2><div id="quotas"></div></section>
  <section><h2>외부 연동 폴백률</h2><div id="externals"></div></section>
  <section><h2>알림</h2><div id="alerts"></div></section>
  <section><h2>학습 신호</h2><div id="signals"></div></section>
  <section><h2>온보딩 응답</h2><div id="prefs"></div></section>
</div>
<script>
const $ = (id) => document.getElementById(id);
const TOKEN_KEY = "coursepilot_admin_token";
$("token").value = localStorage.getItem(TOKEN_KEY) || "";

function esc(v) {
  return String(v ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}
function pct(v) { return (v * 100).toFixed(0) + "%"; }
function rows(head, body) {
  if (!body.length) return '<p class="empty">아직 없음</p>';
  return `<table><thead><tr>${head.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead>`
    + `<tbody>${body.join("")}</tbody></table>`;
}

async function load() {
  const token = $("token").value.trim();
  localStorage.setItem(TOKEN_KEY, token);
  const headers = token ? { "X-Admin-Token": token } : {};
  try {
    const [m, s] = await Promise.all([
      fetch("./metrics", { headers }).then((r) => r.ok ? r.json() : Promise.reject(r.status)),
      fetch("./signals", { headers }).then((r) => r.ok ? r.json() : Promise.reject(r.status)),
    ]);
    $("error").textContent = "";
    render(m, s);
  } catch (status) {
    $("error").textContent = status === 401
      ? "관리자 토큰이 필요합니다." : `지표를 불러오지 못했어요 (${esc(status)})`;
  }
}

function render(m, s) {
  const errClass = m.error_rate >= 0.05 ? "bad" : "ok";
  $("requests").innerHTML = rows(["항목", "값"], [
    `<tr><td>전체 요청</td><td class="num">${m.total_requests}</td></tr>`,
    `<tr><td>오류율</td><td class="num ${errClass}">${pct(m.error_rate)}</td></tr>`,
  ]) + rows(["경로", "요청", "p95"], (m.routes || []).slice(0, 8).map((r) =>
    `<tr><td>${esc(r.route)}</td><td class="num">${r.count}</td><td class="num">${r.p95_ms}ms</td></tr>`));

  $("quotas").innerHTML = rows(["API", "사용/한도", "남음"], (m.quotas || []).map((q) => {
    const cls = q.ratio >= 1 ? "bad" : q.ratio >= 0.8 ? "warn" : "ok";
    return `<tr><td>${esc(q.name)}<div class="bar ${cls}"><span style="width:${Math.min(100, q.ratio * 100)}%"></span></div></td>`
      + `<td class="num">${q.used}/${q.limit}</td><td class="num ${cls}">${q.remaining}</td></tr>`;
  }));

  $("externals").innerHTML = rows(["연동", "성공", "폴백", "폴백률"], (m.externals || []).map((e) => {
    const cls = e.fallback_rate >= 0.5 ? "bad" : e.fallback_rate > 0 ? "warn" : "ok";
    return `<tr><td>${esc(e.name)}</td><td class="num">${e.ok}</td>`
      + `<td class="num">${e.fallback}</td><td class="num ${cls}">${pct(e.fallback_rate)}</td></tr>`;
  }));

  $("alerts").innerHTML = (m.alerts || []).length
    ? rows(["종류", "대상", "값"], m.alerts.map((a) =>
        `<tr><td class="bad">${esc(a.kind)}</td><td>${esc(a.target)}</td><td class="num">${esc(a.value)}</td></tr>`))
    : '<p class="empty ok">임계 초과 없음</p>';

  const sat = s.satisfaction_rate === null ? "표본 없음" : pct(s.satisfaction_rate);
  $("signals").innerHTML = rows(["항목", "값"], [
    `<tr><td>만족도</td><td class="num">${esc(sat)}</td></tr>`,
    `<tr><td>완주</td><td class="num">${s.completed_count}</td></tr>`,
    `<tr><td>완화 제안/적용</td><td class="num">${s.relax_offered}/${s.relax_applied}</td></tr>`,
    `<tr><td>완화 수용률</td><td class="num">${pct(s.relax_acceptance_rate)}</td></tr>`,
  ]);

  const p = s.preferences || {};
  const filled = p.filled_by_question || {};
  $("prefs").innerHTML = rows(["항목", "값"], [
    `<tr><td>가입자</td><td class="num">${p.users ?? 0}</td></tr>`,
    `<tr><td>응답률</td><td class="num">${p.answered_rate === null || p.answered_rate === undefined ? "-" : pct(p.answered_rate)}</td></tr>`,
    ...Object.entries(filled).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="num">${v}</td></tr>`),
  ]);
}

$("refresh").addEventListener("click", load);
$("token").addEventListener("keydown", (e) => { if (e.key === "Enter") load(); });
load();
setInterval(load, 30000);
</script>
</body>
</html>
"""
