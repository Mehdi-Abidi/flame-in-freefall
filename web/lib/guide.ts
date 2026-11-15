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
const HELP_QUESTION = /\b(what is this|what can i do|what do i do|how do i use|how does this work|where am i|guide me|help|this page|this screen|looking at|on (my|the) screen)\b/;
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

const NAMES_AN_EXPERIMENT = /\b(bass|saffire|flex|same|acme|cfi|spice|slice|daft|bre|psi-\d+)\b/;
const ASKS_MEANING = /\b(what|whats|what's|why|how|mean|means|meaning|explain|define|confus\w*|understand|tell me|help me)\b/;

const SMALL_TALK: [RegExp, string][] = [
  [/\bhow (are|r) (you|u)\b|\bhow's it going\b|\bwhat'?s up\b/, "Burning small and steady, thanks. Nothing rises up here, so I stay nice and round. Want me to explain this page?"],
  [/\b(who|what) (are|r) (you|u)\b|\byour name\b/, "I am Wisp, a small flame in freefall and the guide to this site. I know every fire test in NASA's record here and what each word on your screen means."],
  [/\b(thanks|thank you|thx|shukriya)\b/, "Any time. I will be floating right here."],
  [/\b(bye|goodbye|see you)\b/, "Fly safe. I will keep the flame going."],
  [/^(hi+|hey+|hello+|yo|hola|salam|assalam\w*|good (morning|afternoon|evening))\b/, "Hi, I am Wisp, a small flame in freefall. Ask me what anything on this page means, or name a habitat and I will check its cabin."],
];

/** Words a visitor meets on the site. The first entry whose words appear in the question answers it. */
const GLOSSARY: { words: RegExp; text: string; live?: boolean }[] = [
  { words: /\b(never flown|barely flown|not flown|flown|nearby|near (this|my|the) cabin)\b/, live: true, text: "Flown means NASA ran 10 or more tests of that fuel type close to your cabin's air. Barely flown means 1 to 9. Never flown means none, so nobody has evidence either way." },
  { words: /\b(candidate cabins?|8\.2 psi|10\.2 psi)\b/, text: "Those are the cabin atmospheres NASA's own BRE record names for human missions: 10.2 psi with 26.5% oxygen, and 8.2 psi with 34%." },
  { words: /\b(psi (data|repository|database|record|archive)|physical sciences informatics)\b/, text: "PSI is NASA's Physical Sciences Informatics repository, the public archive every number here comes from." },
  { words: /\b(5 (oxygen )?points|20 kpa|tolerance|the box|close to)\b/, text: "A test is near your cabin when its oxygen is within 5 percentage points and its pressure within 20 kPa. On the map that is the box around your cabin." },
  { words: /\b(to breathe|breath\w*|oxygen pressure|partial pressure)\b/, text: "To breathe is the oxygen share times the cabin pressure, compared with sea level. It is how much oxygen your lungs get. A thin cabin with rich oxygen can breathe like Earth." },
  { words: /\b(to burn|oxygen share|richer)\b/, text: "To burn compares the oxygen share with Earth air at 21%. Fire answers to that share, so a 30% cabin burns far more easily than Earth air even when it breathes the same." },
  { words: /\b(sliders?|dials?)\b/, text: "The sliders describe your cabin's air. As you drag them, the box on the map moves, tests fall in or out of it, and the big word updates." },
  { words: /\b(microgravity|freefall|free fall|weightless\w*)\b/, text: "In freefall hot gas does not rise, because nothing is lighter than anything else. A flame becomes a sphere and gets its oxygen by diffusion, which changes how fire spreads." },
  { words: /\bdiffusion\b/, text: "Diffusion is oxygen drifting toward the flame on its own, with no rising air to carry it. It is what feeds a flame in freefall." },
  { words: /\b(gravity|flame shape|illustration|teardrop|sphere|orbit)\b/, text: "The gravity buttons change the flame drawing: a teardrop on Earth, a sphere with no gravity. It is only a picture of shape. Every NASA test here ran in orbit, one experiment has a ground comparison, and none exist for Moon or Mars gravity." },
  { words: /\b(prevent\w*|detect\w*|suppress\w*|pillars?)\b/, text: "NASA's three fire-safety pillars. Prevention is choosing materials that resist burning. Detection is noticing smoke early. Suppression is putting a fire out." },
  { words: /\b(diluents?)\b/, text: "A diluent is a gas mixed into the air to thin out the oxygen. FLEX tested nitrogen, carbon dioxide and helium to see when droplet flames went out." },
  { words: /\b(extinction|extinguish\w*|went out)\b/, text: "Extinction means the flame went out under those conditions. It is recorded for droplet and gas tests, and not for the solid tests." },
  { words: /\b(what is burning|fuel type|(solid|liquid|gas) fuels?)\b/, text: "What is burning picks the kind of fuel: solids are fabrics and plastics, liquids are fuel droplets, gases are burner flames. NASA tested each over a different range, so the answer changes with it." },
  { words: /\b(measured|assumed|planned|basis)\b/, text: "Measured means the oxygen was recorded in that test. Assumed means the experiment ran in cabin air and never logged it, so 21% is filled in and labelled. Planned means a test list with no results yet." },
  { words: /\b(scores?|condition fit|pillar match|material relevance|data richness)\b/, text: "Each investigation gets a score from four visible parts: how close its tests came to the habitat's air, whether it covers your chosen pillar, what it burned, and how much data it holds. No model sets the score." },
  { words: /\b(gap map|dots?|habitat box(es)?)\b/, text: "Each dot is a NASA test, placed by its oxygen and pressure. Boxes are where crews will live. An empty box is the gap." },
  { words: /\b(kpa|psi|pressure)\b/, text: "kPa is air pressure. Sea level is 101 kPa, which is 14.7 psi. A lunar cabin is expected at 70 kPa or less, so it needs a richer oxygen share to breathe." },
  { words: /\b(stages?|journey)\b/, text: "The site is a journey of nine stages. The card at the bottom of every page takes you to the next one." },
];

const OFF_TOPIC = [
  "That one is above my flame grade. I only know fire in freefall. Ask me what a word on this page means, or which experiments matter for a Moon base.",
  "I would need gravity for that one, and I gave it up. Try me on NASA's fire tests, or ask what you are looking at.",
  "No test in NASA's record covers that, and I am made of the record. I can explain this page or check a cabin for you.",
];

/** What Wisp says when a question is outside the site and NASA's record, or when the record cannot be reached. */
export function offTopicReply(message: string): string {
  return OFF_TOPIC[message.trim().length % OFF_TOPIC.length];
}

export function pageName(pathname: string): string {
  return pageFor(pathname).label.replace(/^Open (the )?/, "");
}

export function tourFor(pathname: string): string {
  return pageFor(pathname).tour;
}

/** Answer at once, with no model, when the question is small talk, about a habitat's cabin, about this page, a place
 * to go, the size of the record or a word on the screen. `screenText` is what the page shows right now. */
export function localReply(message: string, pathname: string, data: GuideData, screenText = ""): LocalReply | null {
  const text = message.toLowerCase().trim();

  const chat = SMALL_TALK.find(([words]) => words.test(text));
  if (chat) return { text: chat[1] };

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
    return { text: screenText ? `${page.tour} ${screenText}` : page.tour, link: { href: next.path, label: next.label } };
  }

  if (SIZE_QUESTION.test(text)) {
    const { investigations, records, solidMaxO2, lunarTests } = data.stats;
    return {
      text: `The record holds ${investigations} investigations and ${records.toLocaleString("en-US")} test records. No solid was burned above ${share(solidMaxO2)} oxygen, and ${lunarTests} tests ran at lunar-base conditions, all gas flames.`,
      link: { href: "/evidence/", label: "Open the evidence" },
    };
  }

  const short = text.split(/\s+/).length <= 4;
  if ((ASKS_MEANING.test(text) || short) && !NAMES_AN_EXPERIMENT.test(text)) {
    const entry = GLOSSARY.find((item) => item.words.test(text));
    if (entry) return { text: entry.live && screenText ? `${screenText} ${entry.text}` : entry.text };
  }

  return null;
}

export function suggestionsFor(pathname: string): string[] {
  const here = pageFor(pathname).path;
  const cabin = here === "/lab/" ? "Has a Mars cabin been tested?" : "Has a lunar base cabin been tested?";
  return [cabin, here === "/lab/" ? "What does Never flown mean?" : "What can I do on this page?", "CO2 or helium: which put out flames at lower oxygen?"];
}
