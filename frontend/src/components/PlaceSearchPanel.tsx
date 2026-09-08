"use client";

import { useState } from "react";

import { Button, EmptyState, Input, Skeleton } from "@/components/ui";
import { api } from "@/services/api";
import { useCourseStore } from "@/store/courseStore";
import type { Place } from "@/types";

// 장소 직접 검색 → 코스에 추가. AI 질문을 소모하지 않는 무료 수동 편집 경로.
export default function PlaceSearchPanel({
  disabled = false,
  replaceIndex = null,
  onDone,
}: {
  disabled?: boolean;
  /** 지정되면 추가 대신 해당 순번의 장소를 교체한다. */
  replaceIndex?: number | null;
  onDone?: () => void;
}) {
  const course = useCourseStore((s) => s.course);
  const addPlace = useCourseStore((s) => s.addPlace);
  const replacePlace = useCourseStore((s) => s.replacePlace);
  const replacing = replaceIndex != null;
  const [open, setOpen] = useState(replacing);
  const [q, setQ] = useState("");
  const [region, setRegion] = useState("");
  const [results, setResults] = useState<Place[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const effectiveRegion = (region || course?.region || "").trim();
  const inCourse = new Set(course?.items.map((it) => it.place.id) ?? []);

  async function search() {
    if (!effectiveRegion) {
      setError("지역을 입력해주세요");
      return;
    }
    setError("");
    setLoading(true);
    try {
      setResults(await api.searchPlaces(effectiveRegion, q));
    } catch {
      setError("검색에 실패했어요. 잠시 후 다시 시도해주세요.");
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  if (!open && !replacing) {
    return (
      <Button size="sm" full disabled={disabled} onClick={() => setOpen(true)}>
        + 장소 직접 추가
      </Button>
    );
  }

  return (
    <div
      style={{
        border: "1px solid var(--border)",
        borderRadius: "var(--r-lg)",
        background: "var(--surface)",
        padding: "var(--sp-3)",
      }}
    >
      <div style={{ display: "flex", gap: "var(--sp-2)", marginBottom: "var(--sp-2)" }}>
        {!course?.region && (
          <Input
            aria-label="검색 지역"
            placeholder="지역 (예: 성수동)"
            value={region}
            onChange={(e) => setRegion(e.target.value)}
            style={{ flex: 1, minWidth: 0 }}
          />
        )}
        <Input
          aria-label="장소 검색어"
          placeholder="카페, 전시…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
          style={{ flex: 1, minWidth: 0 }}
        />
        <Button size="sm" variant="primary" onClick={search} disabled={loading}>
          검색
        </Button>
        <Button
          size="sm"
          variant="ghost"
          aria-label="검색 닫기"
          onClick={() => {
            setOpen(false);
            onDone?.();
          }}
        >
          ✕
        </Button>
      </div>

      {error && <div style={{ color: "var(--danger)", fontSize: "var(--fs-sm)" }}>{error}</div>}
      {loading && <Skeleton height={64} />}

      {!loading && results?.length === 0 && !error && (
        <EmptyState title="검색 결과가 없어요" description="다른 키워드로 찾아보세요." />
      )}

      <ul style={{ listStyle: "none", padding: 0, margin: 0, maxHeight: 220, overflowY: "auto" }}>
        {!loading &&
          results?.map((p) => (
            <li
              key={p.id}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: "var(--sp-2)",
                padding: "var(--sp-2) 0",
                borderBottom: "1px solid var(--border)",
              }}
            >
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 600 }}>{p.name}</div>
                <div style={{ color: "var(--text-muted)", fontSize: "var(--fs-sm)" }}>
                  {p.category ?? ""} {p.address ?? ""}
                </div>
              </div>
              <Button
                size="sm"
                variant="primary"
                disabled={disabled || inCourse.has(p.id)}
                onClick={() => {
                  if (replacing) replacePlace(replaceIndex, p.id);
                  else addPlace(p.id);
                  onDone?.();
                }}
              >
                {inCourse.has(p.id) ? "추가됨" : replacing ? "교체" : "추가"}
              </Button>
            </li>
          ))}
      </ul>
    </div>
  );
}
