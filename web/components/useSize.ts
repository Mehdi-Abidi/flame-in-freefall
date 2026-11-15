"use client";

import { useEffect, useRef, useState } from "react";

export function useSize<T extends HTMLElement>(fallbackWidth = 800) {
  const ref = useRef<T | null>(null);
  const [width, setWidth] = useState(fallbackWidth);
  const [measured, setMeasured] = useState(false);
  useEffect(() => {
    const element = ref.current;
    if (!element || typeof ResizeObserver === "undefined") {
      setMeasured(true);
      return;
    }
    const observer = new ResizeObserver(([entry]) => {
      const next = Math.round(entry.contentRect.width);
      if (next > 0) {
        setWidth(next);
        setMeasured(true);
      }
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return { ref, width, measured };
}
