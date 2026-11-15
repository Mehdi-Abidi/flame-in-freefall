import type { Components, Investigation, Pillar, Weights } from "./types";

export const PILLARS: Pillar[] = ["prevention", "detection", "suppression"];
export const DEFAULT_WEIGHTS: Weights = { prevention: 1, detection: 1, suppression: 1 };
export const COMPONENT_ORDER: (keyof Components)[] = ["condition_fit", "pillar_match", "material_relevance", "data_richness"];

export interface RankedRow {
  investigation: Investigation;
  score: number;
  rank: number;
  components: Components;
  contributions: Components;
}

export const MAX_WEIGHT = 3;

export function sanitizeWeights(weights: Partial<Weights>): Weights {
  const clean = { ...DEFAULT_WEIGHTS };
  for (const pillar of PILLARS) {
    const value = Number(weights[pillar]);
    clean[pillar] = Number.isFinite(value) && value >= 0 ? Math.min(value, MAX_WEIGHT) : DEFAULT_WEIGHTS[pillar];
  }
  return PILLARS.some((p) => clean[p] > 0) ? clean : { ...DEFAULT_WEIGHTS };
}

export function pillarMatch(pillars: Pillar[], weights: Weights): number {
  const top = Math.max(...PILLARS.map((p) => weights[p]));
  if (top <= 0) return 0;
  const best = pillars.reduce((max, p) => Math.max(max, weights[p] ?? 0), 0);
  return Math.round((best / top) * 1e4) / 1e4;
}

function accessionNumber(accession: string): number {
  const n = Number(accession.split("-").pop());
  return Number.isFinite(n) ? n : 0;
}

export function rankFor(investigations: Investigation[], scenarioId: string, componentWeights: Components, weights: Partial<Weights>): RankedRow[] {
  const safe = sanitizeWeights(weights);
  const rows = investigations
    .filter((inv) => inv.scores[scenarioId])
    .map((investigation) => {
      const base = investigation.scores[scenarioId].components;
      const components: Components = { ...base, pillar_match: pillarMatch(investigation.pillars, safe) };
      const contributions = Object.fromEntries(
        (Object.keys(components) as (keyof Components)[]).map((key) => [key, componentWeights[key] * components[key]]),
      ) as unknown as Components;
      const score = Math.round(Object.values(contributions).reduce((sum, v) => sum + v, 0) * 1e4) / 1e4;
      return { investigation, score, rank: 0, components, contributions };
    });
  rows.sort((a, b) => b.score - a.score || accessionNumber(a.investigation.accession) - accessionNumber(b.investigation.accession));
  rows.forEach((row, index) => {
    row.rank = index + 1;
  });
  return rows;
}
