import type { Verdict } from "./lab";
import type { Phase } from "./types";

/** What the record holds for one habitat's cabin, worked out when the site is built. */
export interface HabitatReading {
  id: string;
  label: string;
  o2: number;
  kpa: number;
  /** True when the challenge gives no atmosphere for this habitat and the numbers are the team's assumption. */
  assumed: boolean;
  rows: { phase: Phase; verdict: Verdict; close: number }[];
}

export interface GuideData {
  habitats: HabitatReading[];
  names: Record<string, string>;
  stats: { investigations: number; records: number; solidMaxO2: number; lunarTests: number };
}

export interface GuideLink {
  href: string;
  label: string;
}

/** An answer the guide can give at once from the site's own data, with no model involved. */
export interface LocalReply {
  text: string;
  habitat?: HabitatReading;
  link?: GuideLink;
}

const HABITAT_WORDS: [RegExp, string][] = [
  [/\b(moon|lunar)\b/, "lunar_base"],
  [/\brover\b/, "pressurized_rover"],
  [/\b(mars|martian)\b/, "mars_habitat"],
  [/\b(iss|space station|station)\b/, "iss"],
  [/\b(spacesuit|space suit|suit)\b/, "spacesuit"],
];
const CABIN_QUESTION = /\b(test|tested|tests|flown|flew|fly|burn|burned|burnt|safe|safety|cabin|check|cover|covered|gap|show|data)\b/;
const HELP_QUESTION = /\b(what is this|what can i do|what do i do|how do i use|how does this work|where am i|guide me|help)\b/;
const GO_QUESTION = /\b(take me|go to|open|show me|where is|find)\b/;
const SIZE_QUESTION = /\bhow (much|many)\b.*\b(data|tests?|investigations?|experiments?|records?)\b|\bdataset\b/;

const PAGES: { path: string; words: RegExp; label: string; tour: string }[] = [
  { path: "/lab/", words: /\b(lab|playground|cabin lab|simulator)\b/, label: "Open the cabin lab", tour: "Pick a habitat or drag the sliders. The big word says whether NASA flew tests near your cabin, and the list under it shows the closest ones." },
  { path: "/rank/", words: /\b(rank|ranking|ranked)\b/, label: "Open the ranking", tour: "Pick a habitat and drag the three sliders. All the investigations re-order, and each row opens to show why it sits there." },
  { path: "/investigations/", words: /\b(investigations?|experiments?|explorer)\b/, label: "Open the investigations", tour: "Search and filter every investigation. Each one opens a page with its summary, test conditions and papers." },
  { path: "/compare/", words: /\b(compare|comparison|side by side)\b/, label: "Open the comparison", tour: "Choose up to four investigations and read them side by side, with the differences marked." },
  { path: "/ask/", words: /\b(ask page|question page)\b/, label: "Open the Ask page", tour: "Ask in plain English. Every answer comes from NASA's records and cites them." },
  { path: "/earth/", words: /\b(earth|spinoffs?|at home)\b/, label: "Open Back on Earth", tour: "Where the same research is used on Earth, grouped by what it is used for." },
  { path: "/method/", words: /\b(method|how it works|sources|scoring)\b/, label: "Open the method", tour: "How the scores, sources and checks work, and which text a model wrote." },
  { path: "/evidence/", words: /\b(evidence|gap map|map|briefs?|findings)\b/, label: "Open the evidence", tour: "Every test on one map, the gravity comparison, the three briefs and the experiments to fly next." },
  { path: "/", words: /\b(overview|home|mission brief|start)\b/, label: "Open the mission brief", tour: "This is the mission brief. Scroll to watch a flame lose gravity and to see the gap, then open the cabin lab to try a cabin of your own." },
];

function pageFor(pathname: string) {
  return PAGES.find((page) => (page.path === "/" ? pathname === "/" : pathname.startsWith(page.path.replace(/\/$/, "")))) ?? PAGES[PAGES.length - 1];
}

const share = (fraction: number) => `${Number((fraction * 100).toFixed(1))}%`;

/** Answer from the site's own data when the question is about a habitat's cabin, this page, a place to go or the size of the record. */
export function localReply(message: string, pathname: string, data: GuideData): LocalReply | null {
  const text = message.toLowerCase();

  const habitatId = HABITAT_WORDS.find(([words]) => words.test(text))?.[1];
  const habitat = data.habitats.find((h) => h.id === habitatId);
  if (habitat && CABIN_QUESTION.test(text)) {
    return {
      text: `Here is what NASA flew near a ${habitat.label === "ISS" ? "ISS" : habitat.label.toLowerCase()} cabin at ${share(habitat.o2)} oxygen and ${habitat.kpa} kPa.${habitat.assumed ? " That atmosphere is our assumption. The challenge gives none for this habitat." : ""}`,
      habitat,
      link: { href: `/lab/?habitat=${habitat.id}`, label: "Open this cabin in the lab" },
    };
  }

  if (GO_QUESTION.test(text)) {
    const page = PAGES.find((p) => p.words.test(text));
    if (page) return { text: page.tour, link: { href: page.path, label: page.label } };
  }

  if (HELP_QUESTION.test(text)) {
    const page = pageFor(pathname);
    const next = page.path === "/lab/" ? PAGES.find((p) => p.path === "/evidence/")! : PAGES[0];
    return { text: page.tour, link: { href: next.path, label: next.label } };
  }

  if (SIZE_QUESTION.test(text)) {
    const { investigations, records, solidMaxO2, lunarTests } = data.stats;
    return {
      text: `The record holds ${investigations} investigations and ${records.toLocaleString("en-US")} test records. No solid was burned above ${share(solidMaxO2)} oxygen, and ${lunarTests} tests ran at lunar-base conditions, all gas flames.`,
      link: { href: "/evidence/", label: "Open the evidence" },
    };
  }

  return null;
}

export function suggestionsFor(pathname: string): string[] {
  const here = pageFor(pathname).path;
  const cabin = here === "/lab/" ? "Has a Mars cabin been tested?" : "Has a lunar base cabin been tested?";
  return [cabin, "What can I do on this page?", "CO2 or helium: which put out flames at lower oxygen?"];
}
