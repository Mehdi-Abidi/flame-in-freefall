import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { GapMap } from "@/components/GapMap";
import { loadDataset } from "@/lib/data";
import { BASIS_LABEL, PHASE_COLOR, PHASE_LABEL, pct, rangeText } from "@/lib/format";

export const dynamicParams = false;

export function generateStaticParams() {
  return loadDataset().investigations.map((inv) => ({ accession: inv.accession }));
}

export async function generateMetadata({ params }: PageProps<"/investigations/[accession]">): Promise<Metadata> {
  const { accession } = await params;
  const inv = loadDataset().investigations.find((i) => i.accession === accession);
  return inv ? { title: inv.name, description: inv.summary ?? inv.title } : {};
}

function Facts({ title, items, empty = "Not stated in the NASA record" }: { title: string; items: string[]; empty?: string }) {
  return (
    <div>
      <p className="eyebrow mb-2">{title}</p>
      {items.length ? (
        <ul className="flex flex-wrap gap-1.5">
          {items.map((item) => (
            <li key={item} className="rounded-[3px] border border-rule bg-surface px-2 py-0.5 text-[12.5px]">
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-[12.5px] text-muted">{empty}</p>
      )}
    </div>
  );
}

export default async function InvestigationPage({ params }: PageProps<"/investigations/[accession]">) {
  const { accession } = await params;
  const data = loadDataset();
  const inv = data.investigations.find((i) => i.accession === accession);
  if (!inv) notFound();
  const names = Object.fromEntries(data.investigations.map((i) => [i.accession, i.name]));
  const points = data.points.filter((p) => p.a === inv.accession);

  return (
    <article className="mx-auto max-w-[1240px] px-4 pt-10 sm:px-6">
      <nav aria-label="Breadcrumb" className="mono mb-6 text-[12px] text-muted">
        <Link href="/investigations/" className="link-underline hover:text-ink">
          Investigations
        </Link>{" "}
        / {inv.accession}
      </nav>

      <header className="grid gap-6 border-b border-rule pb-8 md:grid-cols-[1fr_auto]">
        <div>
          <h1 className="text-[36px] font-semibold leading-tight tracking-[-0.02em] sm:text-[48px]">{inv.name}</h1>
          <p className="mt-2 max-w-3xl text-[16px] text-ink-2">{inv.title}</p>
          <p className="mt-1 text-[14px] text-muted">
            {inv.projectType ?? "Investigation"}
            {inv.platform && inv.platform !== "ground" && ` aboard ${inv.platform === "ISS" ? "the ISS" : inv.platform}`}
          </p>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            {inv.phases.map((p) => (
              <span key={p} className="inline-flex items-center gap-1.5 rounded-[3px] border border-rule px-2 py-0.5 text-[12.5px]">
                <span aria-hidden="true" className="h-2 w-2 rounded-full" style={{ background: PHASE_COLOR[p] }} />
                {PHASE_LABEL[p]}
              </span>
            ))}
            {(inv.pillars.length ? inv.pillars : ["fundamentals"]).map((p) => (
              <span key={p} className="mono rounded-[3px] border border-ink px-2 py-0.5 text-[11px] uppercase tracking-[0.08em]">
                {p}
              </span>
            ))}
            <span className="mono text-[12px] text-muted">pillars from {inv.pillarSource} tags</span>
          </div>
        </div>
        <div className="flex flex-col items-start gap-2 md:items-end">
          <a href={inv.psiUrl} className="inline-flex items-center gap-2 rounded-[4px] bg-accent px-4 py-2.5 text-[14px] font-medium text-accent-ink">
            Open on NASA PSI <span aria-hidden="true">↗</span>
          </a>
          <Link href={`/compare/?ids=${inv.accession}`} className="text-[13px] text-ink-2 underline-offset-2 hover:text-ink hover:underline">
            Compare with others
          </Link>
        </div>
      </header>

      <div className="grid gap-10 pt-8 lg:grid-cols-[1.35fr_1fr]">
        <section>
          <p className="eyebrow mb-3">Summary</p>
          <p className="max-w-[64ch] text-[17px] leading-relaxed">{inv.summary ?? "No summary available."}</p>
          {inv.objective && <p className="mt-3 max-w-[72ch] text-[14px] leading-relaxed text-ink-2">Objective: {inv.objective}</p>}
          <p className="mono mt-3 max-w-[72ch] text-[12px] text-muted">Drafted by GPT-OSS 20B from NASA&apos;s text. Varied and fixed conditions are computed from the test tables.</p>

          <div className="mt-8 grid gap-6 sm:grid-cols-2">
            <Facts title="Varied between tests" items={inv.varied} />
            <Facts title="Held fixed" items={inv.fixed} />
            <Facts title="Fuels and materials" items={inv.fuels} />
            <Facts title="Sample geometry" items={inv.geometry} />
            <Facts title="Sensors" items={inv.sensors} />
            <Facts title="Measured" items={inv.measurements} />
          </div>

          {inv.earthBenefits.length > 0 && (
            <div className="mt-8">
              <Facts title="Uses on Earth named by NASA" items={inv.earthBenefits} />
            </div>
          )}

          {inv.warnings.length > 0 && (
            <div className="mt-8 border-l-2 border-accent pl-3">
              <p className="eyebrow mb-1 text-accent">Review notes</p>
              <ul className="space-y-1 text-[12.5px] text-ink-2">
                {inv.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </section>

        <aside className="space-y-6">
          <div className="panel p-5">
            <p className="eyebrow mb-3">Conditions on record</p>
            <dl className="grid grid-cols-2 gap-4 text-[13px]">
              <div>
                <dt className="text-muted">Oxygen</dt>
                <dd className="mono mt-1 text-[15px]">{rangeText(inv.o2Range, (v) => pct(v, 1))}</dd>
                {inv.o2Basis && <dd className="mt-0.5 text-[12px] text-ink-2">{BASIS_LABEL[inv.o2Basis] ?? inv.o2Basis}</dd>}
              </div>
              <div>
                <dt className="text-muted">Pressure</dt>
                <dd className="mono mt-1 text-[15px]">{rangeText(inv.kpaRange, (v) => `${Math.round(v)} kPa`)}</dd>
                {inv.kpaBasis && <dd className="mt-0.5 text-[12px] text-ink-2">{BASIS_LABEL[inv.kpaBasis] ?? inv.kpaBasis}</dd>}
              </div>
              <div>
                <dt className="text-muted">Tests</dt>
                <dd className="mono mt-1 text-[15px]">{inv.nTests}</dd>
                {inv.nRecords !== inv.nTests && <dd className="mt-0.5 text-[12px] text-ink-2">{inv.nRecords} table rows incl. test days or planned matrix</dd>}
              </div>
              <div>
                <dt className="text-muted">Sample size</dt>
                <dd className="mono mt-1 text-[15px]">{inv.sampleSize ?? "n/a"}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-muted">Hardware</dt>
                <dd className="mt-1">{inv.hardware ?? "not stated"}</dd>
              </div>
            </dl>
          </div>

          <div className="panel p-5">
            <p className="eyebrow mb-3">Rank by habitat</p>
            <ul className="space-y-2.5">
              {data.scenarios.map((s) => {
                const score = inv.scores[s.id];
                if (!score) return null;
                return (
                  <li key={s.id}>
                    <Link href={`/rank/?habitat=${s.id}`} className="group grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 text-[13px]">
                      <span className="group-hover:underline">{s.label}</span>
                      <span className="mono text-ink-2">
                        #{score.rank} · {Math.round(score.score * 100)}
                      </span>
                      <span className="col-span-2 h-1.5 overflow-hidden rounded-full bg-rule">
                        <span className="block h-full rounded-full bg-ink" style={{ width: `${score.score * 100}%` }} />
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        </aside>
      </div>

      {points.length > 0 && (
        <section className="mt-12">
          <p className="eyebrow mb-3">Its tests on the gap map</p>
          <div className="panel p-4 sm:p-5">
            <GapMap points={data.points} scenarios={data.scenarios} names={names} highlight={inv.accession} height={380} />
          </div>
        </section>
      )}

      {inv.publications.length > 0 && (
        <section className="mt-12">
          <p className="eyebrow mb-3">Publications · {inv.publications.length}</p>
          <ol className="divide-y divide-[color:var(--rule)] border-y border-rule">
            {inv.publications.map((pub, index) => (
              <li key={`${pub.title}-${index}`} className="grid gap-1 py-3 sm:grid-cols-[40px_1fr]">
                <span className="mono text-[12px] text-muted">{String(index + 1).padStart(2, "0")}</span>
                <span className="max-w-[80ch]">
                  <span className="block text-[14px]">{pub.title}</span>
                  {pub.authors && <span className="block text-[12px] text-ink-2">{pub.authors}</span>}
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}
    </article>
  );
}
