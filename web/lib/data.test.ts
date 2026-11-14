import { describe, expect, it } from "vitest";
import { parseCsv } from "./csv";
import { loadDataset } from "./data";

describe("parseCsv", () => {
  it("handles quotes, escaped quotes, commas and CRLF", () => {
    const rows = parseCsv('a,b\r\n1,"x, ""y"""\r\n2,\n');
    expect(rows).toEqual([{ a: "1", b: 'x, "y"' }, { a: "2", b: "" }]);
  });

  it("returns nothing for an empty file", () => {
    expect(parseCsv("")).toEqual([]);
  });
});

describe("loadDataset", () => {
  const data = loadDataset();

  it("merges every investigation with scores for every habitat", () => {
    expect(data.investigations).toHaveLength(24);
    expect(data.scenarios.map((s) => s.id)).toEqual(["iss", "lunar_base", "pressurized_rover", "mars_habitat", "spacesuit"]);
    for (const investigation of data.investigations) {
      expect(Object.keys(investigation.scores).sort()).toEqual(data.scenarios.map((s) => s.id).sort());
    }
  });

  it("computes the same headline numbers as the Python QA", () => {
    expect(data.stats.solidTests).toBe(140);
    expect(data.stats.solidMaxO2).toBeCloseTo(0.222, 3);
    expect(data.stats.lunarTests).toBe(66);
    expect(data.stats.lunarPhases).toEqual(["gas"]);
    expect(data.stats.records).toBe(2127);
  });

  it("only plots points with numeric oxygen and pressure inside physical bounds", () => {
    expect(data.points.length).toBeGreaterThan(1000);
    for (const point of data.points) {
      expect(point.o2).toBeGreaterThan(0);
      expect(point.o2).toBeLessThanOrEqual(1);
      expect(point.kpa).toBeGreaterThan(0);
    }
  });

  it("keeps component weights summing to one", () => {
    const total = Object.values(data.componentWeights).reduce((sum, value) => sum + value, 0);
    expect(total).toBeCloseTo(1, 9);
  });
});
