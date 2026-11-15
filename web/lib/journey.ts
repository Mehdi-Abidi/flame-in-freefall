/** The order a visitor is led through the site. The header, the footer links and every page's next step read from this. */
export const JOURNEY = [
  { path: "/", nav: "Mission", label: "Mission brief", line: "The gap, in four screens" },
  { path: "/lab/", nav: "Cabin lab", label: "Cabin lab", line: "Set a cabin and see what flew there" },
  { path: "/evidence/", nav: "Evidence", label: "Evidence", line: "Every test on one map, and what it shows" },
  { path: "/rank/", nav: "Rank", label: "Rank", line: "Order the 24 investigations for a habitat" },
  { path: "/investigations/", nav: "Investigations", label: "Investigations", line: "Each one in plain words" },
  { path: "/compare/", nav: "Compare", label: "Compare", line: "Up to four, side by side" },
  { path: "/ask/", nav: "Ask", label: "Ask the record", line: "Cited answers from NASA's data" },
  { path: "/earth/", nav: "On Earth", label: "Back on Earth", line: "Where the research lands at home" },
  { path: "/method/", nav: "Method", label: "Method", line: "How every number is made" },
] as const;

export function stageIndex(pathname: string): number {
  const found = JOURNEY.findIndex((stage) => (stage.path === "/" ? pathname === "/" : pathname.startsWith(stage.path.replace(/\/$/, ""))));
  return found < 0 ? 0 : found;
}

export function stageLabel(path: string): string {
  const index = JOURNEY.findIndex((stage) => stage.path === path);
  return `Stage ${index + 1} of ${JOURNEY.length}`;
}
