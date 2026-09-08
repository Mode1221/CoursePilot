"use client";

import { useEffect, useRef, useState } from "react";

import { Button, Input } from "@/components/ui";
import { api } from "@/services/api";
import { useCourseStore } from "@/store/courseStore";
import { toast } from "@/store/toastStore";

const MAX_LEN = 60;

/** 헤더의 코스 이름. 클릭하면 인라인 편집(저장은 PATCH /courses/{id}). */
export default function CourseTitle({
  courseId,
  title,
  userId,
}: {
  courseId: string;
  title: string;
  userId?: string | null;
}) {
  const setCourse = useCourseStore((s) => s.setCourse);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(title);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  async function save() {
    const next = draft.trim();
    setEditing(false);
    if (!next || next === title) return;
    try {
      setCourse(await api.renameCourse(courseId, next, userId ?? undefined));
    } catch {
      setDraft(title);
      toast("이름을 저장하지 못했어요.", "error");
    }
  }

  if (!editing) {
    return (
      <button
        onClick={() => {
          setDraft(title);
          setEditing(true);
        }}
        aria-label="코스 이름 편집"
        style={{
          background: "none",
          border: "none",
          padding: 0,
          font: "inherit",
          fontWeight: 700,
          color: "var(--text)",
          cursor: "pointer",
          textAlign: "left",
        }}
      >
        {title}
      </button>
    );
  }

  return (
    <span style={{ display: "flex", gap: "var(--sp-2)", alignItems: "center", minWidth: 0 }}>
      <Input
        ref={inputRef}
        aria-label="코스 이름"
        value={draft}
        maxLength={MAX_LEN}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") save();
          if (e.key === "Escape") setEditing(false);
        }}
        style={{ padding: "4px 8px", minWidth: 0, flex: 1 }}
      />
      <Button size="sm" variant="primary" onClick={save}>
        저장
      </Button>
    </span>
  );
}
