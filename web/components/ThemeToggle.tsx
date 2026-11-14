"use client";

import { useEffect, useState } from "react";

type Theme = "light" | "dark";
const KEY = "flame-theme";

function systemTheme(): Theme {
  return typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme | null>(null);

  useEffect(() => {
    const stamped = document.documentElement.dataset.theme;
    setTheme(stamped === "dark" || stamped === "light" ? stamped : systemTheme());
  }, []);

  function toggle() {
    const next: Theme = (theme ?? systemTheme()) === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(KEY, next);
    } catch {}
    setTheme(next);
  }

  const label = theme === "dark" ? "Switch to paper mode" : "Switch to night mode";
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      className="mono inline-flex h-8 items-center gap-2 rounded-[4px] border border-rule px-2.5 text-[11px] uppercase tracking-[0.12em] text-ink-2 transition-colors hover:border-rule-strong hover:text-ink"
    >
      <span aria-hidden="true" className="relative inline-block h-3 w-3 overflow-hidden rounded-full border border-current">
        <span className="absolute inset-y-0 right-0 w-1/2 bg-current" />
      </span>
      <span suppressHydrationWarning>{theme === "dark" ? "Night" : theme === "light" ? "Paper" : "Theme"}</span>
    </button>
  );
}

export const themeInitScript = `(function(){try{var t=localStorage.getItem("${KEY}");if(t==="dark"||t==="light"){document.documentElement.dataset.theme=t;}}catch(e){}})();`;
