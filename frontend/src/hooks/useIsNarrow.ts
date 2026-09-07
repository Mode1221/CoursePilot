"use client";

import { useEffect, useState } from "react";

// 좁은 화면(모바일/웹뷰) 감지. SSR 안전(초기 false).
export function useIsNarrow(breakpoint = 720): boolean {
  const [narrow, setNarrow] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia(`(max-width: ${breakpoint}px)`);
    const update = () => setNarrow(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, [breakpoint]);

  return narrow;
}
