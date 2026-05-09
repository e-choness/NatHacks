"use client";

import { Workbox } from "workbox-window";
import * as React from "react";

export function PWARegister() {
  React.useEffect(() => {
    if (typeof window === "undefined") return;
    if (!("serviceWorker" in navigator)) return;
  const wb = new Workbox("/sw.js");
  wb.register().catch((error: any) => console.warn("SW registration failed", error));
  }, []);

  return null;
}
