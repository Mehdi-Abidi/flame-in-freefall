import { Mission } from "@/components/Mission";
import { loadDataset } from "@/lib/data";
import { loadGuideData } from "@/lib/guideData";

const SHOWN_HABITATS = ["iss", "lunar_base", "mars_habitat"];

export default function MissionPage() {
  const data = loadDataset();
  const guide = loadGuideData();
  const solid = data.stats.oxygenByPhase.find((phase) => phase.phase === "solid");
  const top = data.investigations
    .filter((investigation) => investigation.scores.lunar_base)
    .sort((a, b) => a.scores.lunar_base.rank - b.scores.lunar_base.rank)
    .slice(0, 3)
    .map((investigation) => ({ accession: investigation.accession, name: investigation.name, score: Math.round(investigation.scores.lunar_base.score * 100) }));
  return (
    <Mission
      data={{
        investigations: data.stats.investigations,
        records: data.stats.records,
        lunarTests: data.stats.lunarTests,
        solid: { min: solid?.min ?? 0, max: data.stats.solidMaxO2, count: solid?.count ?? data.stats.solidTests },
        habitats: guide.habitats.filter((habitat) => SHOWN_HABITATS.includes(habitat.id)),
        top,
      }}
    />
  );
}
