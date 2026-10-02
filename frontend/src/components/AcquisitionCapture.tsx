"use client";

import { useEffect } from "react";

import { captureAcquisition, isFirstVisit, reportVisit } from "@/services/acquisition";

/** 첫 방문 주소의 출처(src·utm_source)와 같이 정하기 토큰을 기기에 기억하고, 첫 방문이면 서버에 한 번 알린다. 화면에는 아무것도 그리지 않는다. */
export default function AcquisitionCapture() {
  useEffect(() => {
    const first = isFirstVisit();
    const acq = captureAcquisition(window.location.search, window.location.pathname);
    if (first) reportVisit(acq.source); // 기기의 첫 방문만 센다(새로고침·재방문은 안 셈)
  }, []);
  return null;
}
