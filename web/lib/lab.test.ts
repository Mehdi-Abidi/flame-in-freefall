import { describe, expect, it } from "vitest";
import { breathing, flamePath, gap, isClose, presetFor, readCabin, richer, type LabTest } from "./lab";
import { loadLabData } from "./labData";
import { loadDataset } from "./data";

const test = (over: Partial<LabTest>): LabTest => ({ a: "PSI-1", ph: "solid", o2: 0.21, kpa: 101, fuel: "cotton", out: "", ...over });

describe("readCabin", () => {
  it("counts only tests of the same fuel phase within both tolerances", () => {
    const tests = [test({}), test({ o2: 0.26 }), test({ o2: 0.27 }), test({ kpa: 80 }), test({ kpa: null }), test({ ph: "gas" })];
    const reading = readCabin(tests, { o2: 0.21, kpa: 101, phase: "solid" });
    expect(reading.close).toBe(2);
    expect(reading.verdict).toBe("thin");
  });

  it("groups identical tests and puts the nearest first", () => {
    const tests = [test({ o2: 0.4 }), test({}), test({})];
    const [first, second] = readCabin(tests, { o2: 0.21, kpa: 101, phase: "solid" }).nearest;
    expect([first.n, first.gap, second.o2]).toEqual([2, 0, 0.4]);
  });

  it("says how far a cabin sits past the richest test and what went out there", () => {
    const tests = [test({ o2: 0.2, out: "extinction" }), test({ o2: 0.22, out: "burned to completion" })];
    const reading = readCabin(tests, { o2: 0.3, kpa: 70, phase: "solid" });
    expect(reading.verdict).toBe("never");
    expect(reading.beyond).toBeCloseTo(0.08);
    expect([reading.outAtOrAbove, reading.richestOut]).toEqual([0, 0.2]);
  });

  it("treats a missing pressure as one tolerance away and never as close", () => {
    const loose = test({ kpa: null });
    expect(gap(loose, { o2: 0.21, kpa: 101, phase: "solid" })).toBe(1);
    expect(isClose(loose, { o2: 0.21, kpa: 101, phase: "solid" })).toBe(false);
  });
});

describe("the flight record", () => {
  const { tests, smoke } = loadLabData();
  const data = loadDataset();

  it("matches the dashboard's measured-oxygen counts", () => {
    expect(tests.length).toBe(data.stats.oxygenByPhase.reduce((sum, p) => sum + p.count, 0));
    expect(smoke.tests).toBeGreaterThan(0);
  });

  it("has never flown a solid at the lunar preset but has near the ISS preset", () => {
    const lunar = presetFor(data.scenarios.find((s) => s.id === "lunar_base")!);
    const iss = presetFor(data.scenarios.find((s) => s.id === "iss")!);
    const onMoon = readCabin(tests, { ...lunar, phase: "solid" });
    expect(lunar).toEqual({ o2: 0.3, kpa: 70 });
    expect(onMoon.verdict).toBe("never");
    expect(onMoon.beyond).toBeCloseTo(0.3 - data.stats.solidMaxO2);
    expect(readCabin(tests, { ...iss, phase: "solid" }).verdict).toBe("flown");
  });
});

describe("cabin arithmetic", () => {
  it("shows the lunar cabin breathes like Earth and burns richer", () => {
    expect(breathing({ o2: 0.3, kpa: 70.3 })).toBeCloseTo(0.991, 2);
    expect(richer({ o2: 0.3 })).toBeCloseTo(0.429, 2);
  });

  it("draws a round flame with no gravity and a taller one at 1 g", () => {
    const top = (path: string) => Number(path.split(" ")[1]);
    expect(top(flamePath(0))).toBe(104);
    expect(top(flamePath(1))).toBeLessThan(top(flamePath(0.165)));
  });
});
