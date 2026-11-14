import { describe, expect, it } from "vitest";
import { loadDataset } from "./data";
import { basisLines, oxygenMeasured, pointBasis } from "./points";

describe("pointBasis", () => {
  it("separates fully measured tests, tests with only oxygen measured, and the rest", () => {
    expect(pointBasis({ o2Source: "measured", kpaSource: "measured" })).toBe("measured");
    expect(pointBasis({ o2Source: "measured", kpaSource: "nominal_cabin" })).toBe("oxygen");
    expect(pointBasis({ o2Source: "nominal_cabin_air", kpaSource: "nominal_cabin" })).toBe("assumed");
    expect(pointBasis({ o2Source: "planned", kpaSource: "planned" })).toBe("assumed");
    expect(pointBasis({ o2Source: "nominal_cabin_air", kpaSource: "measured" })).toBe("assumed");
  });

  it("says which value was assumed, in plain words", () => {
    expect(basisLines({ o2Source: "measured", kpaSource: "measured" })).toEqual(["Oxygen and pressure measured"]);
    expect(basisLines({ o2Source: "measured", kpaSource: "nominal_cabin" })).toEqual(["Oxygen: measured", "Pressure: assumed cabin pressure"]);
    expect(basisLines({ o2Source: "nominal_cabin_air", kpaSource: "nominal_cabin" })).toEqual(["Oxygen: assumed cabin air", "Pressure: assumed cabin pressure"]);
    expect(basisLines({ o2Source: "planned", kpaSource: "planned" })).toEqual(["Oxygen: planned matrix", "Pressure: planned matrix"]);
    expect(basisLines({ o2Source: "new_tag", kpaSource: "measured" })).toEqual(["Oxygen: new_tag", "Pressure: measured"]);
  });
});

describe("gap map points", () => {
  const data = loadDataset();
  const count = (basis: string, phase?: string) => data.points.filter((p) => pointBasis(p) === basis && (!phase || p.ph === phase)).length;

  it("carries a source tag for oxygen and pressure on every point", () => {
    for (const point of data.points) {
      expect(point.o2Source).not.toBe("");
      expect(point.kpaSource).not.toBe("");
    }
  });

  it("splits the 1,968 plotted tests by what was measured", () => {
    expect(data.points).toHaveLength(1968);
    expect(count("measured")).toBe(981);
    expect(count("oxygen")).toBe(140);
    expect(count("assumed")).toBe(847);
  });

  it("keeps the solid tests behind the 22.2% headline visible when only measured oxygen is shown", () => {
    const solids = data.points.filter((p) => p.ph === "solid" && oxygenMeasured(p));
    expect(solids).toHaveLength(data.stats.solidTests);
    expect(Math.max(...solids.map((p) => p.o2))).toBeCloseTo(data.stats.solidMaxO2, 9);
    expect(count("measured", "solid")).toBe(0);
    expect(count("oxygen", "solid")).toBe(140);
  });
});
