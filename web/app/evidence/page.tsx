import type { Metadata } from "next";
import { BriefCards } from "@/components/BriefCards";
import { DiluentChart } from "@/components/DiluentChart";
import { GapMap } from "@/components/GapMap";
import { GravityTable } from "@/components/GravityTable";
import { NextTests } from "@/components/NextTests";
import { OxygenRuler } from "@/components/OxygenRuler";
import { PartialGravityNote } from "@/components/PartialGravityNote";
import { PageIntro, SectionHeader } from "@/components/Section";
import { loadDataset } from "@/lib/data";
import { flexByDiluent } from "@/lib/flex";
import { stageLabel } from "@/lib/journey";
import { nextTests } from "@/lib/nextTests";

export const metadata: Metadata = { title: "Evidence" };

const PARTS = [
  { id: "gap", label: "The gap" },
  { id: "gravity", label: "Gravity" },
  { id: "findings", label: "Findings" },
  { id: "next", label: "Next flights" },
];

export default function EvidencePage() {
  const data = loadDataset();
  const names = Object.fromEntries(data.investigations.map((i) => [i.accession, i.name]));
  const lunar = data.scenarios.find((s) => s.id === "lunar_base");
  const efield = data.investigations.find((i) => i.accession === "PSI-22");
  const efieldOnMap = data.points.some((p) => p.a === efield?.accession);

  return (
    <div className="mx-auto max-w-[1240px] px-4 pt-12 sm:px-6">
      <PageIntro kicker={`${stageLabel("/evidence/")} · Evidence`} title="The evidence">
        Every test NASA flew, what gravity changed, what the record says and what to fly next.
      </PageIntro>
      <nav aria-label="On this page" className="mb-14 flex flex-wrap gap-2">
        {PARTS.map((part, index) => (
          <a key={part.id} href={`#${part.id}`} className="mono rounded-[2px] border border-rule-strong px-3 py-2 text-[12px] uppercase tracking-[0.1em] text-ink-2 transition-colors hover:border-accent hover:text-accent">
            0{index + 1} {part.label}
          </a>
        ))}
      </nav>

      <section id="gap" className="scroll-mt-32">
        <SectionHeader step="01 · The gap" title="Where the tests stop">
          Oxygen in every test, then every test by oxygen and pressure. No point in the lunar box is a solid.
        </SectionHeader>
        {lunar && (
          <div className="mb-10 max-w-[820px]">
            <OxygenRuler phases={data.stats.oxygenByPhase} lunar={lunar.o2} lunarTests={data.stats.lunarTests} lunarPhases={data.stats.lunarPhases} lunarMaxKpa={lunar.kpa[1]} />
          </div>
        )}
        <div className="panel p-4 sm:p-5">
          <GapMap points={data.points} scenarios={data.scenarios} names={names} selectedScenario={lunar?.id} solidMaxO2={data.stats.solidMaxO2} />
        </div>
      </section>

      <section id="gravity" className="scroll-mt-32 pt-20">
        <SectionHeader step="02 · Gravity" title="Gravity changes the answer">
          SAFFIRE-II burned the same samples in orbit and on the ground. Thin silicone burned completely on Earth and barely in orbit.
        </SectionHeader>
        <GravityTable rows={data.gravity} notes={data.gravityNotes} />
        <PartialGravityNote efield={efield} efieldOnMap={efieldOnMap} />
      </section>

      {data.briefs.length > 0 && (
        <section id="findings" className="scroll-mt-32 pt-20">
          <SectionHeader step="03 · Findings" title="What the record says">
            One brief per fire-safety pillar. Every finding cites its NASA record.
          </SectionHeader>
          <BriefCards briefs={data.briefs} names={names} />
          <div className="mt-4 max-w-[820px]">
            <DiluentChart rows={flexByDiluent()} />
          </div>
        </section>
      )}

      <section id="next" className="scroll-mt-32 pt-20">
        <SectionHeader step="04 · Next flights" title="What to fly next">
          Four experiments that would close these gaps, each backed by the test tables.
        </SectionHeader>
        <NextTests tests={nextTests(data)} names={names} />
      </section>
    </div>
  );
}
