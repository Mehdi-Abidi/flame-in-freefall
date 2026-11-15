import { loadDataset } from "./data";
import { HABITAT_SHORT_LABEL } from "./format";
import type { GuideData } from "./guide";
import { LAB_PHASES, isAssumed, presetFor, readCabin } from "./lab";
import { loadLabData } from "./labData";

/** The small set of facts the guide can answer from at once. Counted from the same tests as the cabin lab. */
export function loadGuideData(): GuideData {
  const data = loadDataset();
  const { tests } = loadLabData();
  return {
    habitats: data.scenarios.map((scenario) => {
      const preset = presetFor(scenario);
      return {
        id: scenario.id,
        label: HABITAT_SHORT_LABEL[scenario.id] ?? scenario.label,
        ...preset,
        assumed: isAssumed(scenario),
        rows: LAB_PHASES.map((phase) => {
          const reading = readCabin(tests, { ...preset, phase });
          return { phase, verdict: reading.verdict, close: reading.close };
        }),
      };
    }),
    names: Object.fromEntries(data.investigations.map((i) => [i.accession, i.name])),
    stats: { investigations: data.stats.investigations, records: data.stats.records, solidMaxO2: data.stats.solidMaxO2, lunarTests: data.stats.lunarTests },
  };
}
