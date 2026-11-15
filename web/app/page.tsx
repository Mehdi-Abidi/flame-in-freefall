import Link from "next/link";
import { BriefCards } from "@/components/BriefCards";
import { GapMap } from "@/components/GapMap";
import { GravityTable } from "@/components/GravityTable";
import { NextTests } from "@/components/NextTests";
import { OxygenRuler } from "@/components/OxygenRuler";
import { PartialGravityNote } from "@/components/PartialGravityNote";
import { SectionHeader } from "@/components/Section";
import { loadDataset } from "@/lib/data";
import { compact, pct } from "@/lib/format";
import { nextTests } from "@/lib/nextTests";

const WHERE_NEXT = [
  { href: "/lab/", title: "Cabin lab", line: "Set oxygen, pressure and gravity. See what flew there." },
  { href: "/rank/", title: "Rank", line: "Order all 24 investigations for one habitat." },
  { href: "/compare/", title: "Compare", line: "Put up to four side by side." },
  { href: "/earth/", title: "Back on Earth", line: "Where the same research lands at home." },
];

export default function OverviewPage() {
  const data = loadDataset();
  const names = Object.fromEntries(data.investigations.map((i) => [i.accession, i.name]));
  const lunar = data.scenarios.find((s) => s.id === "lunar_base");
  const efield = data.investigations.find((i) => i.accession === "PSI-22");
  const efieldOnMap = data.points.some((p) => p.a === efield?.accession);

  return (
    <>
      <section className="border-b border-rule">
        <div className="mx-auto max-w-[1240px] px-4 pb-14 pt-14 sm:px-6 md:pt-20">
          <h1 className="max-w-[19ch] text-[40px] font-semibold leading-[1.04] tracking-[-0.02em] sm:text-[56px] md:text-[64px]">
            Solid-material fire tests in orbit stopped at {pct(data.stats.solidMaxO2, 1)} oxygen. A lunar base will breathe 30%.
          </h1>
          <div className="mt-10 grid gap-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-14">
            <div>
              <p className="max-w-[44ch] text-[17px] leading-relaxed text-ink-2">
                NASA&apos;s archive holds {data.stats.investigations} fire investigations. Set a cabin of your own and see what was burned there, and what never was.
              </p>
              <div className="mt-7 flex flex-wrap gap-3">
                <Link href="/lab/" className="inline-flex h-11 items-center rounded-[4px] bg-accent px-5 text-[14px] font-medium text-accent-ink transition-transform hover:-translate-y-px active:translate-y-px">
                  Open the cabin lab
                </Link>
                <Link href="/rank/" className="inline-flex h-11 items-center rounded-[4px] border border-rule-strong px-5 text-[14px] font-medium transition-[transform,border-color] hover:-translate-y-px hover:border-ink active:translate-y-px">
                  Rank the experiments
                </Link>
              </div>
              <p className="mono mt-8 text-[12px] leading-relaxed text-muted">
                {data.stats.records.toLocaleString("en-US")} test records · {compact(data.stats.rawFiles)} raw files linked at NASA, not copied
              </p>
            </div>
            {lunar && (
              <OxygenRuler phases={data.stats.oxygenByPhase} lunar={lunar.o2} lunarTests={data.stats.lunarTests} lunarPhases={data.stats.lunarPhases} lunarMaxKpa={lunar.kpa[1]} />
            )}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[1240px] px-4 pt-16 sm:px-6">
        <SectionHeader step="01 · The gap" title="The gap map">
          Every test, placed by oxygen and pressure. The boxes are where crews will live. Few points land in the lunar box, and none are solids.
        </SectionHeader>
        <div className="panel p-4 sm:p-5">
          <GapMap points={data.points} scenarios={data.scenarios} names={names} selectedScenario={lunar?.id} solidMaxO2={data.stats.solidMaxO2} />
        </div>
      </section>

      <section className="mx-auto max-w-[1240px] px-4 pt-16 sm:px-6">
        <SectionHeader step="02 · Gravity" title="Gravity changes the answer">
          SAFFIRE-II burned the same samples in orbit and on the ground. Thin silicone burned completely on Earth and barely in orbit. Cotton-fiberglass
          burned its full length in both.
        </SectionHeader>
        <GravityTable rows={data.gravity} notes={data.gravityNotes} />
        <PartialGravityNote efield={efield} efieldOnMap={efieldOnMap} />
      </section>

      {data.briefs.length > 0 && (
        <section className="mx-auto max-w-[1240px] px-4 pt-16 sm:px-6">
          <SectionHeader step="03 · The findings" title="What the data says">
            One brief per fire-safety pillar. Every finding cites its NASA record.
          </SectionHeader>
          <BriefCards briefs={data.briefs} names={names} />
        </section>
      )}

      <section className="mx-auto max-w-[1240px] px-4 pt-16 sm:px-6">
        <SectionHeader step="04 · Next flights" title="What to test next">
          Four experiments that would close these gaps, each backed by the test tables.
        </SectionHeader>
        <NextTests tests={nextTests(data)} names={names} />
      </section>

      <section className="mx-auto max-w-[1240px] px-4 pt-16 sm:px-6">
        <SectionHeader step="05 · Your turn" title="Take it further" />
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {WHERE_NEXT.map((item) => (
            <li key={item.href}>
              <Link href={item.href} className="panel block h-full p-5 transition-[transform,border-color] hover:-translate-y-0.5 hover:border-rule-strong active:translate-y-0">
                <span className="block text-[17px] font-semibold leading-snug">{item.title}</span>
                <span className="mt-2 block text-[14px] leading-relaxed text-ink-2">{item.line}</span>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
