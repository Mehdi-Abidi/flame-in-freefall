/** What the page is showing right now, in one plain sentence, so the guide can talk about it. Pages that change as
 * the visitor works (the cabin lab) keep this up to date. Other pages leave it empty and the guide uses the page's own description. */
let current = "";

export const screen = {
  set(text: string) {
    current = text;
  },
  get() {
    return current;
  },
};

/** The plain-words note of the part of the page nearest the middle of the window. Parts of a page carry one in a
 * `data-wisp` attribute. When several contain the middle, the smallest wins, because it is the most specific. */
export function sectionInView(): string {
  if (typeof document === "undefined") return "";
  const middle = window.innerHeight / 2;
  let best = "";
  let bestScore = Infinity;
  for (const part of document.querySelectorAll<HTMLElement>("[data-wisp]")) {
    const box = part.getBoundingClientRect();
    if (box.bottom < 0 || box.top > window.innerHeight) continue;
    const away = box.top <= middle && box.bottom >= middle ? 0 : Math.min(Math.abs(box.top - middle), Math.abs(box.bottom - middle));
    const score = away * 100000 + box.height;
    if (score < bestScore) {
      bestScore = score;
      best = part.dataset.wisp ?? "";
    }
  }
  return best;
}
