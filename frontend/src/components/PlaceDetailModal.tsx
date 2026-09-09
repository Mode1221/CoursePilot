"use client";

import { useEffect, useRef, useState } from "react";

import { Badge, Button, Skeleton } from "@/components/ui";
import { hoursFreshnessLabel, yearsOpen as placeYearsOpen } from "@/services/placeFacts";
import { naverMapUrl } from "@/services/mapLink";
import { api } from "@/services/api";
import { useCourseStore } from "@/store/courseStore";
import { useUserStore } from "@/store/userStore";
import { toast } from "@/store/toastStore";
import type { Place } from "@/types";


// 장소 상세 모달 (4-2). 리뷰 요약은 RAG(협찬 필터 후) 결과.
export default function PlaceDetailModal({
  place,
  onClose,
  editable = false,
}: {
  place: Place;
  onClose: () => void;
  editable?: boolean;
}) {
  const addPlace = useCourseStore((s) => s.addPlace);
  const courseItems = useCourseStore((s) => s.course?.items);
  const [summary, setSummary] = useState<string>("불러오는 중…");
  const [aspects, setAspects] = useState<{ pros: string[]; cons: string[] }>({ pros: [], cons: [] });
  const [myStars, setMyStars] = useState<number | null>(null);
  const [revisit, setRevisit] = useState(false);
  const userId = useUserStore((s) => s.userId);
  const [related, setRelated] = useState<Place[]>([]);
  const closeRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const titleId = `place-${place.id}`;
  const yearsOpen = placeYearsOpen(place);
  const hoursFreshness = hoursFreshnessLabel(place);
  const inCourse = new Set((courseItems ?? []).map((it) => it.place.id));

  useEffect(() => {
    // 장소를 빠르게 바꾸면 이전 요청 응답이 늦게 와 다른 장소의 요약이 남을 수 있다
    let cancelled = false;
    setSummary("불러오는 중…");
    setAspects({ pros: [], cons: [] });
    setRelated([]);
    api
      .reviewSummary(place.id, place.name)
      .then((r) => {
        if (cancelled) return;
        setSummary(r.summary);
        setAspects({ pros: r.pros ?? [], cons: r.cons ?? [] });
      })
      .catch(() => {
        if (!cancelled) setSummary("리뷰를 불러오지 못했습니다.");
      });
    api
      .relatedPlaces(place.id)
      .then((places) => {
        if (!cancelled) setRelated(places);
      })
      .catch(() => {
        if (!cancelled) setRelated([]);
      });
    return () => {
      cancelled = true;
    };
  }, [place.id, place.name]);

  useEffect(() => {
    closeRef.current?.focus(); // 열릴 때 포커스 이동
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key === "Tab") {
        // 포커스 트랩: 모달 내부 포커스 순환
        const items = dialogRef.current?.querySelectorAll<HTMLElement>(
          'button, [href], input, [tabindex]:not([tabindex="-1"])',
        );
        if (!items || items.length === 0) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(9, 16, 21, .55)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 10,
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(e) => e.stopPropagation()}
        className="cp-enter"
        style={{
          background: "var(--surface)",
          color: "var(--text)",
          borderRadius: "var(--r-lg)",
          padding: "var(--sp-6)",
          width: 380,
          maxWidth: "92%",
          maxHeight: "85vh",
          overflow: "auto",
          boxShadow: "var(--shadow-2)",
        }}
      >
        <h3 id={titleId} style={{ marginTop: 0 }}>{place.name}</h3>
        {place.category && <Badge>{place.category}</Badge>}
        {place.address && <div style={{ color: "var(--text-muted)", fontSize: "var(--fs-sm)", marginTop: "var(--sp-2)" }}>{place.address}</div>}
        {place.rating != null && (
          <div>
            ⭐ {place.rating.toFixed(1)}
            {place.rating_count != null && (
              <span style={{ color: "var(--text-muted)", fontSize: "var(--fs-sm)" }}>
                {" "}
                ({place.rating_count.toLocaleString()}명)
              </span>
            )}
          </div>
        )}
        {yearsOpen != null && (
          <div style={{ fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
            영업 {yearsOpen}년차
          </div>
        )}
        {place.price != null && <div style={{ fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>1인 약 {place.price.toLocaleString()}원{place.price_estimated ? " (추정)" : ""}</div>}
        {(place.open_time || place.close_time) && (
          <div style={{ fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
            영업 {place.open_time?.slice(0, 5)}~{place.close_time?.slice(0, 5)}
            {/* 브레이크는 헛걸음으로 이어지는 정보라 영업시간 옆에 붙인다 */}
            {place.break_start && place.break_end && (
              <> · 브레이크 {place.break_start.slice(0, 5)}~{place.break_end.slice(0, 5)}</>
            )}
            {/* 언제 확인한 정보인지 밝혀야 사용자가 스스로 판단할 수 있다 */}
            {hoursFreshness && <> · {hoursFreshness}</>}
          </div>
        )}
        {place.hours_unverified && (
          <div style={{ fontSize: "var(--fs-sm)", color: "var(--text-muted)" }}>
            영업시간 확인 필요 — 방문 전 확인해 주세요
          </div>
        )}
        {(place.fact_tags?.length || place.caution_tags?.length) && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--sp-1)", marginTop: "var(--sp-2)" }}>
            {place.fact_tags?.map((t) => (
              <Badge key={`f-${t}`} tone="brand">
                {t} 가능
              </Badge>
            ))}
            {place.caution_tags?.map((t) => (
              <Badge key={`fc-${t}`} tone="warn">
                {t} 주의
              </Badge>
            ))}
          </div>
        )}
        <h4>리뷰 요약</h4>
        {summary === "불러오는 중…" ? (
          <div style={{ display: "grid", gap: "var(--sp-2)" }}>
            <Skeleton height={12} />
            <Skeleton height={12} width="80%" />
          </div>
        ) : (
          <>
            {(aspects.pros.length > 0 || aspects.cons.length > 0) && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--sp-1)", marginBottom: "var(--sp-2)" }}>
                {aspects.pros.map((t) => (
                  <Badge key={`p-${t}`} tone="brand">
                    👍 {t}
                  </Badge>
                ))}
                {aspects.cons.map((t) => (
                  <Badge key={`c-${t}`} tone="warn">
                    ⚠ {t}
                  </Badge>
                ))}
              </div>
            )}
            <p style={{ color: "var(--text-muted)", fontSize: "var(--fs-sm)" }}>{summary}</p>
          </>
        )}

        <h4>다녀왔다면 별점을 남겨주세요</h4>
        <div role="group" aria-label="별점" style={{ display: "flex", gap: 4 }}>
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              aria-label={`${n}점`}
              onClick={() => {
                const prev = myStars;
                setMyStars(n);
                api.ratePlace(place.id, n, userId ?? undefined).catch(() => {
                  setMyStars(prev); // 저장 실패는 UI 도 되돌린다
                  toast("별점을 저장하지 못했어요.", "error");
                });
              }}
              style={{
                border: "none",
                background: "none",
                cursor: "pointer",
                fontSize: 22,
                color: myStars != null && n <= myStars ? "#f5a623" : "var(--border)",
              }}
            >
              ★
            </button>
          ))}
        </div>
        {myStars != null && <p style={{ color: "var(--brand-strong)", fontSize: "var(--fs-sm)" }}>평가 감사합니다!</p>}

        {related.length > 0 && (
          <>
            <h4>함께 가요</h4>
            <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "grid", gap: "var(--sp-2)" }}>
              {related.map((r) => {
                const already = inCourse.has(r.id);
                return (
                <li
                  key={r.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: "var(--sp-2)",
                    fontSize: "var(--fs-sm)",
                    color: "var(--text-muted)",
                  }}
                >
                  <span>
                    {r.name}
                    {r.category ? ` · ${r.category}` : ""}
                  </span>
                  {editable && (
                    <Button
                      size="sm"
                      disabled={already}
                      onClick={() => {
                        addPlace(r.id);
                        onClose();
                      }}
                    >
                      {already ? "추가됨" : "추가"}
                    </Button>
                  )}
                </li>
                );
              })}
            </ul>
          </>
        )}

        <Button
          aria-pressed={revisit}
          onClick={() => {
            if (revisit) return;
            setRevisit(true);
            api.revisit(place.id, userId ?? undefined).catch(() => {
              setRevisit(false);
              toast("기록을 저장하지 못했어요.", "error");
            });
          }}
          size="sm"
          variant={revisit ? "primary" : "secondary"}
          style={{ marginTop: "var(--sp-2)", marginRight: "var(--sp-2)" }}
        >
          {revisit ? "또 가고 싶은 곳 ✓" : "또 가고 싶어요"}
        </Button>

        <a
          href={naverMapUrl(place)}
          target="_blank"
          rel="noopener noreferrer"
          style={{ marginRight: "var(--sp-2)" }}
        >
          <Button size="sm">지도에서 열기</Button>
        </a>

        <Button ref={closeRef} onClick={onClose} size="sm" style={{ marginTop: "var(--sp-2)" }}>
          닫기
        </Button>
      </div>
    </div>
  );
}
