import type { Phase, Pillar } from "./types";

export const PHASE_LABEL: Record<Phase, string> = { solid: "Solid", liquid: "Liquid", gas: "Gas", dust: "Dust" };
export const PHASE_COLOR: Record<Phase, string> = { solid: "var(--s1)", liquid: "var(--s2)", gas: "var(--s3)", dust: "var(--muted)" };
export const PLOTTED_PHASES: Phase[] = ["solid", "liquid", "gas"];

export const PILLAR_LABEL: Record<Pillar, string> = { prevention: "Prevention", detection: "Detection", suppression: "Suppression" };

export const HABITAT_SHORT_LABEL: Record<string, string> = {
  iss: "ISS",
  lunar_base: "Lunar base",
  pressurized_rover: "Rover",
  mars_habitat: "Mars",
  spacesuit: "Spacesuit",
};

export const BASIS_LABEL: Record<string, string> = {
  measured: "measured",
  planned: "planned matrix",
  approximate: "approximate",
  test_day_list: "test-day list",
  nominal_cabin_air: "assumed cabin air",
  nominal_cabin: "assumed cabin pressure",
  nominal_1atm: "assumed 1 atm",
};

export function pct(fraction: number, digits = 0): string {
  return `${(fraction * 100).toFixed(digits)}%`;
}

export function kpa(value: number): string {
  return `${Math.round(value)} kPa`;
}

export function rangeText(range: [number, number] | null, format: (v: number) => string): string {
  if (!range) return "not recorded";
  const [a, b] = range;
  return Math.abs(a - b) < 1e-9 ? format(a) : `${format(a)} to ${format(b)}`;
}

export function compact(value: number): string {
  return new Intl.NumberFormat("en", { notation: value >= 10000 ? "compact" : "standard", maximumFractionDigits: 1 }).format(value);
}
