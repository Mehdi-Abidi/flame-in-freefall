import type { Metadata } from "next";
import { PageIntro, SectionHeader } from "@/components/Section";
import { loadDataset } from "@/lib/data";
import { pct } from "@/lib/format";

export const metadata: Metadata = { title: "Method" };

const STEPS = [
  { code: "A", title: "Fetch", body: "The PSI search API lists the 24 combustion investigations. We download their metadata and the experimental tables, under 1 MB. The 16 TB of raw video and sensor files stay on NASA's servers." },
  { code: "B", title: "Normalize", body: "21 tables in different units (mmHg, atm, bar, percent, mole fraction) become one table of 2,127 rows. Every oxygen and pressure value carries a tag saying whether it was measured, planned or assumed." },
  { code: "C", title: "Extract", body: "An open model (GPT-OSS 20B on Groq) reads NASA's text for each investigation. Facts the tables already prove are handed to it as ground truth, and anything it names that is not in the source is flagged." },
  { code: "D", title: "Rank", body: "A deterministic score, no AI involved, rates every investigation for each habitat. The same code runs in Python for the data files and in your browser for the sliders, and a test proves they agree." },
];

const RULES = [
  "Assumed values are never shown as measured. Hollow dots, basis labels and the ranking all keep the difference.",
  "Which conditions varied and which stayed fixed comes from the tables, not the model.",
  "A detection pillar is dropped unless the source mentions smoke, aerosols, particles, dust or detectors.",
  "Summaries that call a varied condition constant fail the data checks.",
  "Every page links back to the NASA record it came from.",
];

export default function MethodPage() {
  const data = loadDataset();
  const w = data.componentWeights;
  return (
    <div className="mx-auto max-w-[1240px] px-4 pt-12 sm:px-6">
      <PageIntro title="Method">
        How NASA&apos;s raw records become the rankings and briefs on this site, and where each number comes from.
      </PageIntro>

      <SectionHeader title="Pipeline">
        Four steps turn NASA&apos;s raw repository into this dashboard. Each runs from a script in the repository and is checked automatically on
        every change.
      </SectionHeader>
      <ol className="mb-16 grid gap-4 md:grid-cols-4">
        {STEPS.map((step) => (
          <li key={step.code} className="ticks border border-rule bg-surface p-5">
            <p className="mono text-[12px] text-accent">STEP {step.code}</p>
            <p className="mt-2 text-[17px] font-semibold">{step.title}</p>
            <p className="mt-2 text-[13px] leading-relaxed text-ink-2">{step.body}</p>
          </li>
        ))}
      </ol>

      <SectionHeader title="The score">
        Each investigation gets a score from 0 to 1 for a habitat, shown as 0 to 100. The parts and their weights:
      </SectionHeader>
      <div className="mb-16 overflow-x-auto rounded-[6px] border border-rule bg-surface">
        <table className="w-full min-w-[640px] border-collapse text-[13.5px]">
          <thead>
            <tr className="eyebrow border-b border-rule text-left">
              <th className="px-4 py-3 font-normal">Part</th>
              <th className="px-4 py-3 text-right font-normal">Weight</th>
              <th className="px-4 py-3 font-normal">How it is measured</th>
            </tr>
          </thead>
          <tbody>
            {[
              ["Condition fit", w.condition_fit, "Distance from each test to the habitat's oxygen and pressure box, counted in tolerances of 0.05 oxygen fraction and 20 kPa. Measured values count fully, assumed cabin values half. Half the best test, half the typical test."],
              ["Pillar match", w.pillar_match, "1.0 when the investigation covers your highest-weighted pillar, scaled down for lower priorities. The best single pillar counts, so extra tags do not inflate a score."],
              ["Material", w.material_relevance, "Solid 1.0, liquid 0.7, gas 0.5, dust 0.4. Habitat fires start in solids."],
              ["Data richness", w.data_richness, "Number of tests, raw files and publications, each log-scaled against the largest investigation."],
            ].map(([name, weight, how]) => (
              <tr key={name as string} className="border-b border-rule last:border-0">
                <td className="px-4 py-3 font-medium">{name}</td>
                <td className="mono px-4 py-3 text-right">{Math.round((weight as number) * 100)}%</td>
                <td className="px-4 py-3 leading-relaxed text-ink-2">{how}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <SectionHeader title="Habitat targets">
        Taken from the challenge text. Where we had to assume something, it says so.
      </SectionHeader>
      <div className="mb-16 grid gap-4 md:grid-cols-2">
        {data.scenarios.map((s) => (
          <div key={s.id} className="panel p-5">
            <div className="flex items-baseline justify-between gap-3">
              <p className="text-[16px] font-semibold">{s.label}</p>
              <p className="mono text-[12px] text-ink-2">
                {pct(s.o2[0])} to {pct(s.o2[1])} · {s.kpa[0]} to {s.kpa[1]} kPa
              </p>
            </div>
            <p className="mt-2 text-[13px] leading-relaxed text-ink-2">{s.source}</p>
            {s.assumptions.map((a) => (
              <p key={a} className="mt-2 border-l-2 border-accent pl-2.5 text-[12.5px] text-ink-2">
                {a}
              </p>
            ))}
          </div>
        ))}
      </div>

      <SectionHeader title="Honesty rules">
        The rules that keep a fast hackathon build trustworthy. Each is enforced by an automated check.
      </SectionHeader>
      <ul className="mb-16 grid gap-3 md:grid-cols-2">
        {RULES.map((rule, i) => (
          <li key={rule} className="flex gap-3 border-t border-rule pt-3 text-[14px] leading-relaxed">
            <span className="mono text-[12px] text-accent">R{i + 1}</span>
            {rule}
          </li>
        ))}
      </ul>

      <SectionHeader title="Limits and AI use">
        No partial-gravity combustion data is in PSI yet. Microgravity and 1 g results bound what may happen on the Moon or Mars, and future data
        from the Lunar-g Combustion Investigation and Flammability of Materials on the Moon will fill that gap. The E-FIELD experiment mimicked
        partial gravity with electric fields. AI use: GPT-OSS 20B (via Groq) drafted the investigation summaries from NASA&apos;s text, and an AI
        coding assistant helped write the software. All scores are deterministic and every claim links to its NASA source.
      </SectionHeader>
    </div>
  );
}
