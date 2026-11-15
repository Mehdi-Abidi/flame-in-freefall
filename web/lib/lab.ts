import type { Phase, Range, Scenario } from "./types";

/** Same tolerances as data/domain/scenarios.json: a test is near a cabin within 0.05 oxygen and 20 kPa. */
export const TOLERANCE = { o2: 0.05, kpa: 20 };
export const EARTH = { o2: 0.21, kpa: 101.3 };
export const LAB_PHASES: Phase[] = ["solid", "liquid", "gas"];

const WENT_OUT = new Set(["extinction", "self-extinguished"]);
const EPS = 1e-9;

/** One flight test with a measured oxygen value. */
export interface LabTest {
  a: string;
  ph: Phase;
  o2: number;
  kpa: number | null;
  fuel: string;
  out: string;
}

export interface Cabin {
  o2: number;
  kpa: number;
  phase: Phase;
}

export type Verdict = "flown" | "thin" | "never";

export interface NearTest extends LabTest {
  n: number;
  gap: number;
}

export interface Reading {
  close: number;
  verdict: Verdict;
  recorded: number;
  wentOut: number;
  nearest: NearTest[];
  range: Range | null;
  beyond: number;
  below: number;
  outAtOrAbove: number;
  richestOut: number | null;
}

export const GRAVITIES = [
  { id: "orbit", label: "Orbit", g: 0 },
  { id: "moon", label: "Moon", g: 0.165 },
  { id: "mars", label: "Mars", g: 0.378 },
  { id: "earth", label: "Earth", g: 1 },
] as const;

export type GravityId = (typeof GRAVITIES)[number]["id"];

export function wentOut(test: LabTest): boolean {
  return WENT_OUT.has(test.out);
}

/** Distance from a test to the cabin, counted in tolerances. A test with no pressure on record sits one tolerance away on that axis. */
export function gap(test: LabTest, cabin: Cabin): number {
  const oxygen = (test.o2 - cabin.o2) / TOLERANCE.o2;
  const pressure = test.kpa === null ? 1 : (test.kpa - cabin.kpa) / TOLERANCE.kpa;
  return Math.hypot(oxygen, pressure);
}

export function isClose(test: LabTest, cabin: Cabin): boolean {
  return test.kpa !== null && Math.abs(test.o2 - cabin.o2) <= TOLERANCE.o2 + EPS && Math.abs(test.kpa - cabin.kpa) <= TOLERANCE.kpa + EPS;
}

/** What the flight record holds for one cabin and one kind of fuel. Counts only, no prediction. */
export function readCabin(tests: LabTest[], cabin: Cabin): Reading {
  const same = tests.filter((t) => t.ph === cabin.phase);
  const close = same.filter((t) => isClose(t, cabin));
  const recorded = close.filter((t) => t.out !== "");

  const groups = new Map<string, NearTest>();
  for (const test of same) {
    const key = [test.a, test.o2, test.kpa, test.fuel, test.out].join("|");
    const seen = groups.get(key);
    if (seen) seen.n += 1;
    else groups.set(key, { ...test, n: 1, gap: gap(test, cabin) });
  }
  const nearest = [...groups.values()].sort((x, y) => x.gap - y.gap || y.n - x.n || x.a.localeCompare(y.a)).slice(0, 4);

  const oxygen = same.map((t) => t.o2);
  const range: Range | null = oxygen.length ? [Math.min(...oxygen), Math.max(...oxygen)] : null;
  const out = same.filter(wentOut);

  return {
    close: close.length,
    verdict: close.length >= 10 ? "flown" : close.length > 0 ? "thin" : "never",
    recorded: recorded.length,
    wentOut: recorded.filter(wentOut).length,
    nearest,
    range,
    beyond: range && cabin.o2 - range[1] > EPS ? cabin.o2 - range[1] : 0,
    below: range && range[0] - cabin.o2 > EPS ? range[0] - cabin.o2 : 0,
    outAtOrAbove: out.filter((t) => t.o2 >= cabin.o2 - EPS).length,
    richestOut: out.length ? Math.max(...out.map((t) => t.o2)) : null,
  };
}

/** Oxygen partial pressure against sea level: what the crew breathes. */
export function breathing(cabin: Pick<Cabin, "o2" | "kpa">): number {
  return (cabin.o2 * cabin.kpa) / (EARTH.o2 * EARTH.kpa);
}

/** Oxygen share against Earth air: what a fire sees. */
export function richer(cabin: Pick<Cabin, "o2">): number {
  return cabin.o2 / EARTH.o2 - 1;
}

/** The point a habitat button sets: the middle of the habitat's box, so "near this cabin" means inside the box
 * the rest of the site draws. The spacesuit is context only and sits at its stated 100% oxygen. */
export function presetFor(scenario: Scenario): { o2: number; kpa: number } {
  const middle = (r: Range) => (r[0] + r[1]) / 2;
  return { o2: scenario.contextOnly ? scenario.o2[1] : Math.round(middle(scenario.o2) * 100) / 100, kpa: Math.round(middle(scenario.kpa)) };
}

/** True when the challenge text gives no atmosphere for a habitat, so its box is the team's assumption. */
export function isAssumed(scenario: Scenario): boolean {
  return /^no atmosphere is given/i.test(scenario.source);
}

/** Outline of the drawn flame: a sphere with no gravity, a teardrop at 1 g. An illustration of buoyancy, not a simulation. */
export function flamePath(g: number, scale = 1): string {
  const stretch = Math.sqrt(Math.max(0, Math.min(1, g)));
  const cx = 100;
  const cy = 150;
  const w = (46 - 14 * stretch) * scale;
  const h = (46 + 92 * stretch) * scale;
  const d = (46 - 10 * stretch) * scale;
  const k = 0.5523;
  const tip = 1 - 0.9 * stretch;
  const f = (n: number) => n.toFixed(1);
  return (
    `M${f(cx)} ${f(cy - h)} ` +
    `C${f(cx + w * k * tip)} ${f(cy - h)} ${f(cx + w)} ${f(cy - h * k)} ${f(cx + w)} ${f(cy)} ` +
    `C${f(cx + w)} ${f(cy + d * k)} ${f(cx + w * k)} ${f(cy + d)} ${f(cx)} ${f(cy + d)} ` +
    `C${f(cx - w * k)} ${f(cy + d)} ${f(cx - w)} ${f(cy + d * k)} ${f(cx - w)} ${f(cy)} ` +
    `C${f(cx - w)} ${f(cy - h * k)} ${f(cx - w * k * tip)} ${f(cy - h)} ${f(cx)} ${f(cy - h)}Z`
  );
}
