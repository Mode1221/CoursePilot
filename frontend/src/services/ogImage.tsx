// 미리보기(OG) 이미지 한 장을 그린다(next/og). 서버에서만 쓴다.
//
// 기본 글꼴에는 한글이 없다 — 한글 부분집합 글꼴(public/fonts/og-sans-kr-bold.woff, OFL)을 함께 싣는다.
// 글꼴을 못 읽으면 한글이 두부(□)로 나오는 대신 영문 카드로 그린다.
import { readFile } from "node:fs/promises";
import path from "node:path";

import { ImageResponse } from "next/og";

import { DEFAULT_CARD, type OgCard } from "@/services/ogText";

export const OG_SIZE = { width: 1200, height: 630 };
export const OG_CONTENT_TYPE = "image/png";

const FONT_FILE = path.join("public", "fonts", "og-sans-kr-bold.woff");
const FONT_NAME = "OgSansKR";

let fontPromise: Promise<ArrayBuffer | null> | null = null;

function loadFont(): Promise<ArrayBuffer | null> {
  // standalone 서버·개발 서버·빌드 모두 작업 디렉터리 아래 public/ 이 있다(Dockerfile 이 public 을 복사)
  fontPromise ??= readFile(path.join(process.cwd(), FONT_FILE))
    .then((buf) => buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer)
    .catch(() => {
      fontPromise = null; // 다음 요청에서 다시 시도
      return null;
    });
  return fontPromise;
}

const LATIN_CARD: OgCard = {
  eyebrow: "픽앤어스",
  headline: "Plan a date course together",
  sub: "Answer a 30-second card. No sign-up.",
};

const INK = "#171412";
const MUTED = "#6b665f";
const PAPER = "#f8f8f7";
const CHIP = "#ebe8e1";
const ACCENT = "#ff7a59";

export async function renderOgCard(card: OgCard | null | undefined): Promise<ImageResponse> {
  const font = await loadFont();
  const c = font ? card ?? DEFAULT_CARD : LATIN_CARD;
  // 한 줄에 72px 로 16자 남짓 들어간다 — 길면 줄이고, 줄바꿈은 단어 단위로(글자 하나만 다음 줄로 넘어가지 않게)
  const long = c.headline.length > 16;
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "64px 72px",
          background: PAPER,
          color: INK,
          fontFamily: font ? FONT_NAME : undefined,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ width: 20, height: 20, borderRadius: 10, background: ACCENT, display: "flex" }} />
          <div style={{ fontSize: 30, fontWeight: 700, letterSpacing: -0.5, display: "flex" }}>픽앤어스</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 22 }}>
          <div style={{ fontSize: 30, color: MUTED, display: "flex" }}>{c.eyebrow}</div>
          <div
            style={{
              fontSize: long ? 60 : 72,
              fontWeight: 700,
              lineHeight: 1.2,
              letterSpacing: -1.5,
              display: "flex",
              flexWrap: "wrap",
              wordBreak: "keep-all",
              maxWidth: 1040,
            }}
          >
            {c.headline}
          </div>
          {c.chips && c.chips.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center" }}>
              {c.chips.map((chip, i) => (
                <div key={`${chip}-${i}`} style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  {i > 0 && <div style={{ fontSize: 28, color: MUTED, display: "flex" }}>→</div>}
                  <div
                    style={{
                      display: "flex",
                      fontSize: 30,
                      padding: "10px 22px",
                      borderRadius: 999,
                      background: CHIP,
                    }}
                  >
                    {chip}
                  </div>
                </div>
              ))}
            </div>
          )}
          {c.sub && <div style={{ fontSize: 34, color: MUTED, display: "flex" }}>{c.sub}</div>}
        </div>
        <div style={{ display: "flex", fontSize: 26, color: MUTED }}>
          {font ? "둘이 같이 정하는 데이트 코스" : "coursepilot"}
        </div>
      </div>
    ),
    {
      ...OG_SIZE,
      fonts: font ? [{ name: FONT_NAME, data: font, weight: 700, style: "normal" }] : undefined,
      headers: { "Cache-Control": "public, max-age=300, s-maxage=300" },
    },
  );
}
