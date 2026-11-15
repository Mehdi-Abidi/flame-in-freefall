import { pct } from "./format";
import { burnExtent } from "./gravity";
import type { Dataset } from "./types";

export interface NextTest {
  id: string;
  title: string;
  evidence: string;
  proposal: string;
  buildsOn: string[];
}

const exact = (fraction: number) => pct(fraction, 1).replace(".0%", "%");

function materials(data: Dataset): string[] {
  const names = data.gravity.flatMap((row) => row.material.split("&").map((part) => part.trim()));
  return [...new Set(names.map((name) => name.replace("Cotton-Fiberglass", "cotton-fiberglass").replace("Silicone", "silicone")))];
}

function listOf(items: string[]): string {
  return items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

export function nextTests(data: Dataset): NextTest[] {
  const lunar = data.scenarios.find((s) => s.id === "lunar_base");
  if (!lunar) return [];
  const [lo, hi] = lunar.o2;
  const [kLo, kHi] = lunar.kpa;
  const band = `${pct(lo)} to ${pct(hi)} oxygen`;
  const solid = data.stats.oxygenByPhase.find((p) => p.phase === "solid");
  const flex = data.stats.flexExtinction;
  const smoke = data.investigations.filter((i) => i.accession === "PSI-102" || i.accession === "PSI-101");
  const smokeTests = smoke.reduce((sum, i) => sum + i.nTests, 0);
  const smokeAssumed = smoke.length === 2 && smoke.every((i) => i.o2Basis === "nominal_cabin_air");
  const silicone = data.gravity.find((row) => row.sample === "2-1");
  const sibal = data.gravity.find((row) => row.sample === "2-5");
  const gravityFlip =
    silicone && sibal && burnExtent(silicone.microBurn) === "none" && burnExtent(silicone.oneGBurn) === "full" && burnExtent(sibal.microBurn) === "full";

  const tests: NextTest[] = [];
  if (solid) {
    tests.push({
      id: "solids",
      title: "Burn solids in lunar-base air",
      evidence: `No solid-material test in PSI ran above ${exact(solid.max)} oxygen. The ${data.stats.lunarTests} tests at lunar-base conditions all burned ${listOf(data.stats.lunarPhases)}.`,
      proposal: `Measure flame spread over the materials already flown, ${listOf(materials(data))}, at ${band} and ${Math.round(kLo)} to ${Math.round(kHi)} kPa.`,
      buildsOn: ["PSI-25", "PSI-99"],
    });
  }
  if (flex.count) {
    tests.push({
      id: "extinction",
      title: "Check that extinction still works on solids",
      evidence: `FLEX droplet flames went out ${flex.count} times, as low as ${exact(flex.lowestO2)} oxygen, but only ${flex.atLunarO2} of those were at ${pct(lo)} oxygen or more, and all were liquid droplets.`,
      proposal: `Repeat FLEX's nitrogen, helium and carbon dioxide dilution on burning solids at ${band} to find the oxygen level at which they go out.`,
      buildsOn: ["PSI-69", "PSI-68", "PSI-25"],
    });
  }
  if (smokeAssumed && smokeTests) {
    tests.push({
      id: "smoke",
      title: "Measure smoke at lunar oxygen and pressure",
      evidence: `SAME and SAME-R measured smoke in ${smokeTests} tests, all in cabin air at an assumed 21% oxygen.`,
      proposal: `Measure smoke particle size at ${band} and reduced pressure, the air a lunar smoke detector would have to work in.`,
      buildsOn: ["PSI-102", "PSI-101", "PSI-115"],
    });
  }
  if (gravityFlip) {
    tests.push({
      id: "gravity",
      title: "Fill the partial-gravity column",
      evidence: "In SAFFIRE-II, thin silicone burned fully on Earth but barely in microgravity, while cotton-fiberglass burned fully in both. PSI has no partial-gravity data yet.",
      proposal: "Burn the SAFFIRE-II materials at lunar gravity, the kind of data the challenge expects from LUCI and FM2, to see which way each material goes.",
      buildsOn: ["PSI-99", "PSI-22"],
    });
  }
  return tests;
}
