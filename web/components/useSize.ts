"use client";

import { useLayoutEffect, useRef, useState } from "react";

export function useSize<T extends HTMLElement>(fallbackWidth = 800) {
  const ref = useRef<T | null>(null);
  const [width, setWidth] = useState(fallbackWidth);
  const [measured, setMeasured] = useState(false);
  useLayoutEffect(() => {
    const element = ref.current;
    const initial = element ? Math.round(element.getBoundingClientRect().width) : 0;
    if (initial > 0) setWidth(initial);
    setMeasured(true);
    if (!element || typeof ResizeObserver === "undefined") return;
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
