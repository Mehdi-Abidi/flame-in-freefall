import { describe, expect, it } from "vitest";
import { loadDataset } from "./data";
import { DEFAULT_WEIGHTS, MAX_WEIGHT, pillarMatch, rankFor, sanitizeWeights } from "./rank";

const data = loadDataset();

describe("rankFor matches the Python ranking engine", () => {
  for (const scenario of data.scenarios) {
    it(`reproduces every score and rank for ${scenario.id} with default weights`, () => {
      const rows = rankFor(data.investigations, scenario.id, data.componentWeights, DEFAULT_WEIGHTS);
      expect(rows).toHaveLength(24);
      for (const row of rows) {
        const python = row.investigation.scores[scenario.id];
        expect(row.score).toBeCloseTo(python.score, 3);
        expect(row.rank).toBe(python.rank);
      }
    });
  }
});

describe("weights", () => {
  it("re-ranks when detection is the only priority", () => {
    const top = rankFor(data.investigations, "lunar_base", data.componentWeights, { prevention: 0, detection: 1, suppression: 0 })[0];
    expect(top.investigation.pillars).toContain("detection");
  });

  it("does not reward extra pillar tags", () => {
    expect(pillarMatch(["prevention"], DEFAULT_WEIGHTS)).toBe(pillarMatch(["prevention", "suppression"], DEFAULT_WEIGHTS));
    expect(pillarMatch(["detection"], { prevention: 2, detection: 1, suppression: 0 })).toBe(0.5);
    expect(pillarMatch([], DEFAULT_WEIGHTS)).toBe(0);
  });

  it("falls back to defaults for invalid or all-zero weights", () => {
    expect(sanitizeWeights({ prevention: -1, detection: Number.NaN })).toEqual(DEFAULT_WEIGHTS);
    expect(sanitizeWeights({ prevention: 0, detection: 0, suppression: 0 })).toEqual(DEFAULT_WEIGHTS);
    expect(sanitizeWeights({ prevention: 3 })).toEqual({ prevention: 3, detection: 1, suppression: 1 });
  });

  it("contributions add up to the score", () => {
    for (const row of rankFor(data.investigations, "iss", data.componentWeights, { suppression: 2 })) {
      const total = Object.values(row.contributions).reduce((sum, v) => sum + v, 0);
      expect(total).toBeCloseTo(row.score, 3);
    }
  });
});

describe("weights from the URL", () => {
  it("caps a weight at the slider maximum", () => {
    expect(sanitizeWeights({ prevention: 9, detection: 1, suppression: 1 }).prevention).toBe(MAX_WEIGHT);
  });
});
