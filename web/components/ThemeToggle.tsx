"use client";

import { useSyncExternalStore } from "react";

type Theme = "light" | "dark";
const KEY = "flame-theme";
const QUERY = "(prefers-color-scheme: dark)";

function currentTheme(): Theme {
  const stamped = document.documentElement.dataset.theme;
  if (stamped === "dark" || stamped === "light") return stamped;
  return window.matchMedia(QUERY).matches ? "dark" : "light";
}

function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  const media = window.matchMedia(QUERY);
  media.addEventListener("change", onChange);
  return () => {
    observer.disconnect();
    media.removeEventListener("change", onChange);
  };
}

export function ThemeToggle() {
  const theme = useSyncExternalStore<Theme | null>(subscribe, currentTheme, () => null);

  function toggle() {
    const next: Theme = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(KEY, next);
    } catch {}
  }

  const label = theme === "dark" ? "Switch to paper mode" : "Switch to night mode";
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      className="mono inline-flex h-8 items-center gap-2 rounded-[4px] border border-rule px-2.5 text-[12px] uppercase tracking-[0.12em] text-ink-2 transition-colors hover:border-rule-strong hover:text-ink"
    >
      <span aria-hidden="true" className="relative inline-block h-3 w-3 overflow-hidden rounded-full border border-current">
        <span className="absolute inset-y-0 right-0 w-1/2 bg-current" />
      </span>
      <span>{theme === "dark" ? "Night" : theme === "light" ? "Paper" : "Theme"}</span>
    </button>
  );
}

export const themeInitScript = `(function(){try{var t=localStorage.getItem("${KEY}");document.documentElement.dataset.theme=(t==="dark"||t==="light")?t:"dark";}catch(e){}})();`;
