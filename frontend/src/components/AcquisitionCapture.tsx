"use client";

import { useEffect } from "react";

import { captureAcquisition } from "@/services/acquisition";

/** 첫 방문 주소의 출처(src·utm_source)와 같이 정하기 토큰을 기기에 기억한다. 화면에는 아무것도 그리지 않는다. */
export default function AcquisitionCapture() {
  useEffect(() => {
    captureAcquisition(window.location.search, window.location.pathname);
  }, []);
  return null;
}
