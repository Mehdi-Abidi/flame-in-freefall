import { describe, expect, it } from "vitest";
import { loadDataset } from "./data";
import { burnExtent, referencedNotes, thicknessLabel } from "./gravity";

describe("burnExtent", () => {
  it("reads the cells NASA's SAFFIRE-II table uses", () => {
    expect(burnExtent("Complete")).toBe("full");
    expect(burnExtent("~ 0")).toBe("none");
    expect(burnExtent("0")).toBe("none");
    expect(burnExtent("~ 0 (Nomex)")).toBe("none");
    expect(burnExtent("7.6 cm")).toBe("partial");
    expect(burnExtent("~ 10 cm (note 3)")).toBe("partial");
    expect(burnExtent("5 cm & 0 (note 2)")).toBe("partial");
  });

  it("counts a burn of the whole 29 cm sample as full", () => {
    expect(burnExtent("29 cm")).toBe("full");
    expect(burnExtent("28.9 cm")).toBe("partial");
    expect(burnExtent("10 cm", 10)).toBe("full");
  });

  it("does not guess when a cell is empty or is not a length", () => {
    expect(burnExtent("")).toBe("unknown");
    expect(burnExtent("   ")).toBe("unknown");
    expect(burnExtent("n/a")).toBe("unknown");
    expect(burnExtent("Note 4")).toBe("unknown");
  });
});

describe("SAFFIRE-II gravity comparison", () => {
  const data = loadDataset();

  it("labels all nine samples the way the Overview text describes them", () => {
    const extents = Object.fromEntries(data.gravity.map((row) => [row.sample, [burnExtent(row.microBurn), burnExtent(row.oneGBurn)]]));
    expect(extents).toEqual({
      "2-1": ["none", "full"],
      "2-2": ["none", "partial"],
      "2-3": ["none", "none"],
      "2-4": ["none", "full"],
      "2-5": ["full", "full"],
      "2-6": ["full", "full"],
      "2-7": ["partial", "none"],
      "2-8": ["partial", "full"],
      "2-9": ["partial", "full"],
    });
  });
});

describe("E-FIELD facts quoted in the partial-gravity note", () => {
  const data = loadDataset();
  const efield = data.investigations.find((i) => i.accession === "PSI-22");

  it("is a gas-flame investigation with test days but no recorded atmosphere", () => {
    expect(efield?.name).toBe("ACME E-FIELD Flames");
    expect(efield?.phases).toEqual(["gas"]);
    expect(efield?.fuels).toEqual(["methane", "ethylene"]);
    expect(efield?.nTests).toBe(0);
    expect(efield?.nRecords).toBe(20);
    expect(efield?.o2Range).toBeNull();
    expect(efield?.kpaRange).toBeNull();
  });

  it("has no points on the gap map", () => {
    expect(data.points.filter((p) => p.a === "PSI-22")).toHaveLength(0);
  });
});

describe("SAFFIRE-II table notes", () => {
  it("shows NASA's notes that the burn cells refer to", () => {
    const data = loadDataset();
    const shown = referencedNotes(data.gravity, data.gravityNotes);
    expect(shown.map((n) => n.note)).toEqual(["2", "3", "4"]);
    expect(shown[0].text).toContain("Nomex was not ignited");
  });
});

describe("thickness labels", () => {
  it("marks NASA's leading-zero cells instead of guessing a value", () => {
    expect(thicknessLabel("037 mm")).toBe("037 mm (as written in NASA's table)");
    expect(thicknessLabel("0.27 mm")).toBe("0.27 mm");
    expect(thicknessLabel("See Fig. 5")).toBe("See Fig. 5");
  });
});
