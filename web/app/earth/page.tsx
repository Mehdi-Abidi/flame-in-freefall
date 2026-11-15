import { stageLabel } from "@/lib/journey";
import type { Metadata } from "next";
import Link from "next/link";
import { PageIntro, SectionHeader } from "@/components/Section";
import { loadDataset } from "@/lib/data";
import { EARTH_THEMES, benefitText } from "@/lib/earth";

export const metadata: Metadata = { title: "Back on Earth" };

const HISTORY = [
  {
    when: "January 1967",
    title: "Apollo 1",
    body: "A fire swept through the Apollo 1 command module during a ground test with the cabin full of pure oxygen. All three crew died. It is why oxygen levels in a cabin are treated as a design decision.",
  },
  {
    when: "February 1997",
    title: "Mir",
    body: "An oxygen-generating canister caught fire aboard the Mir space station. The crew put it out, working through thick smoke in a closed cabin.",
  },
];

export default function EarthPage() {
  const data = loadDataset();
  const byAccession = new Map(data.investigations.map((i) => [i.accession, i]));
  const total = EARTH_THEMES.reduce((sum, t) => sum + t.accessions.length, 0);

  return (
    <div className="mx-auto max-w-[1240px] px-4 pt-12 sm:px-6">
      <PageIntro kicker={`${stageLabel("/earth/")} · On Earth`} title="Back on Earth">
        {total} of the {data.investigations.length} investigations name uses on Earth in their own NASA records.
      </PageIntro>

      <section className="mb-16">
        <SectionHeader title="Why spacecraft fire matters" />
        <ol className="grid gap-x-10 gap-y-10 md:grid-cols-2">
          {HISTORY.map((event) => (
            <li key={event.title} className="border-t-2 border-ink pt-4">
              <p className="text-[13px] text-ink-2">{event.when}</p>
              <p className="mt-1 text-[17px] font-semibold">{event.title}</p>
              <p className="mt-2 max-w-[60ch] text-[14px] leading-relaxed text-ink-2">{event.body}</p>
            </li>
          ))}
        </ol>
      </section>

      {EARTH_THEMES.map((theme) => (
        <section key={theme.id} className="mb-16" aria-labelledby={`theme-${theme.id}`}>
          <h2 id={`theme-${theme.id}`} className="text-[24px] font-semibold leading-tight tracking-[-0.01em]">
            {theme.title}
          </h2>
          <p className="mt-2 max-w-[60ch] text-[15px] leading-relaxed text-ink-2">{theme.intro}</p>
          <ul className="mt-6 divide-y divide-[color:var(--rule)] border-y border-rule">
            {theme.accessions.map((accession) => {
              const inv = byAccession.get(accession);
              if (!inv) return null;
              return (
                <li key={accession} className="grid gap-2 py-4 md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] md:gap-8">
                  <Link href={`/investigations/${accession}/`} className="group">
                    <span className="block text-[15px] font-semibold group-hover:underline">{inv.name}</span>
                    <span className="mono text-[12px] text-muted">{accession}</span>
                  </Link>
                  <p className="max-w-[64ch] text-[14px] leading-relaxed text-ink-2">{inv.earthBenefits.map(benefitText).join(". ")}.</p>
                </li>
              );
            })}
          </ul>
        </section>
      ))}

      <p className="max-w-[64ch] text-[13px] leading-relaxed text-muted">
        The uses listed for each investigation were drafted by GPT-OSS 20B from that investigation&apos;s NASA research-impact text. Open an
        investigation to read its summary and the link to its NASA record.
      </p>
    </div>
  );
}
