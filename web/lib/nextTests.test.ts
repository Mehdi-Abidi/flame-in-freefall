import { describe, expect, it } from "vitest";
import { loadDataset } from "./data";
import { nextTests } from "./nextTests";

describe("recommended next tests", () => {
  const data = loadDataset();
  const tests = nextTests(data);
  const byId = Object.fromEntries(tests.map((t) => [t.id, t]));

  it("recommends four tests, each built on investigations that exist", () => {
    expect(tests.map((t) => t.id)).toEqual(["solids", "extinction", "smoke", "gravity"]);
    const known = new Set(data.investigations.map((i) => i.accession));
    for (const test of tests) for (const accession of test.buildsOn) expect(known.has(accession)).toBe(true);
  });

  it("quotes the numbers the data gives", () => {
    expect(byId.solids.evidence).toContain("above 22.2% oxygen");
    expect(byId.solids.evidence).toContain("The 20 tests at lunar-base conditions all burned gas");
    expect(byId.solids.proposal).toContain("silicone");
    expect(byId.solids.proposal).toContain("30% to 40% oxygen and 30 to 70 kPa");
    expect(byId.extinction.evidence).toBe(
      "FLEX droplet flames went out 186 times, as low as 12% oxygen, but only 2 of those were at 30% oxygen or more, and all were liquid droplets.",
    );
    expect(byId.smoke.evidence).toBe("SAME and SAME-R measured smoke in 129 tests, all in cabin air at an assumed 21% oxygen.");
  });
});
