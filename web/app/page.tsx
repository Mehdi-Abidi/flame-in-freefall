import Link from "next/link";
import { BriefCards } from "@/components/BriefCards";
import { GapMap } from "@/components/GapMap";
import { GravityTable } from "@/components/GravityTable";
import { OxygenRuler } from "@/components/OxygenRuler";
import { SectionHeader } from "@/components/Section";
import { loadDataset } from "@/lib/data";
import { compact, pct } from "@/lib/format";

export default function OverviewPage() {
  const data = loadDataset();
  const names = Object.fromEntries(data.investigations.map((i) => [i.accession, i.name]));
  const lunar = data.scenarios.find((s) => s.id === "lunar_base");

  return (
    <>
      <section className="border-b border-rule">
        <div className="mx-auto max-w-[1240px] px-4 pb-14 pt-14 sm:px-6 md:pt-20">
          <h1 className="max-w-[19ch] text-[40px] font-semibold leading-[1.04] tracking-[-0.02em] sm:text-[56px] md:text-[64px]">
            Solid-material fire tests in orbit stopped at {pct(data.stats.solidMaxO2, 1)} oxygen. A lunar base will breathe 30%.
          </h1>
          <div className="mt-10 grid gap-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-14">
            <div>
              <p className="max-w-[52ch] text-[17px] leading-relaxed text-ink-2">
                Every solid-material burn in NASA&apos;s microgravity record ran in air or thinner. Moon habitats will run richer in oxygen to make
                spacewalks easier, and materials burn faster there. This dashboard ranks each of the {data.stats.investigations} experiments for the
                habitat you are designing and shows exactly where the data runs out.
              </p>
              <p className="mt-6 text-[15px]">
                <Link href="/rank/" className="link-underline font-medium text-accent">
                  Rank them for your habitat
                </Link>
                <span className="text-ink-2"> or read the gap map below.</span>
              </p>
              <p className="mt-8 max-w-[52ch] text-[13px] leading-relaxed text-muted">
                Built from {data.stats.records.toLocaleString()} test records. The {compact(data.stats.rawFiles)} raw files, {data.stats.rawTerabytes.toFixed(1)} TB
                of video and sensor data, stay on NASA&apos;s servers and are linked, not copied.
              </p>
            </div>
            {lunar && (
              <OxygenRuler phases={data.stats.oxygenByPhase} lunar={lunar.o2} lunarTests={data.stats.lunarTests} lunarPhases={data.stats.lunarPhases} />
            )}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-[1240px] px-4 pt-16 sm:px-6">
        <SectionHeader title="The gap map">
          Every test with a recorded atmosphere, placed by oxygen and pressure. The shaded boxes are where crews will live. Notice how few points
          land in the lunar box, and that none of them are solids.
        </SectionHeader>
        <div className="panel p-4 sm:p-5">
          <GapMap points={data.points} scenarios={data.scenarios} names={names} selectedScenario={lunar?.id} solidMaxO2={data.stats.solidMaxO2} />
        </div>
      </section>

      <section className="mx-auto max-w-[1240px] px-4 pt-16 sm:px-6">
        <SectionHeader title="Gravity changes the answer">
          SAFFIRE-II burned the same samples in a departing Cygnus cargo ship that were also tested on the ground. Thin silicone burned completely
          on Earth but barely at all in microgravity, while cotton-fiberglass fabric burned its full length in both. Screening materials at 1 g can
          mislead in both directions.
        </SectionHeader>
        <GravityTable rows={data.gravity} />
      </section>

      {data.briefs.length > 0 && (
        <section className="mx-auto max-w-[1240px] px-4 pt-16 sm:px-6">
          <SectionHeader title="What the data says">
            One brief per fire-safety pillar. Each finding cites the NASA investigations it comes from, and code checked every number, citation
            and claim against the data before it was published. A domain review is still pending.
          </SectionHeader>
          <BriefCards briefs={data.briefs} names={names} />
        </section>
      )}

      <section className="mx-auto max-w-[1240px] px-4 pt-16 sm:px-6">
        <SectionHeader title="Where to next" />
        <div className="grid gap-4 md:grid-cols-3">
          {[
            { href: "/rank/", title: "Rank for a habitat", body: "Pick ISS, lunar base, rover or Mars, weight prevention, detection and suppression, and watch the list re-order." },
            { href: "/investigations/", title: "Read the investigations", body: "Plain-language summaries, what was varied, what was held fixed, sensors, and every publication." },
            { href: "/compare/", title: "Compare side by side", body: "Put up to four investigations next to each other. Rows that differ are marked." },
          ].map((card) => (
            <Link key={card.href} href={card.href} className="group panel block p-5 transition-transform hover:-translate-y-0.5">
              <p className="text-[16px] font-semibold">
                {card.title} <span className="inline-block text-accent transition-transform group-hover:translate-x-1" aria-hidden="true">→</span>
              </p>
              <p className="mt-2 text-[14px] leading-relaxed text-ink-2">{card.body}</p>
            </Link>
          ))}
        </div>
      </section>
    </>
  );
}
