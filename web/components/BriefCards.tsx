import Link from "next/link";
import { PILLAR_LABEL } from "@/lib/format";
import type { Brief } from "@/lib/types";

const PILLAR_CODE: Record<string, string> = { prevention: "P", detection: "D", suppression: "S" };

export function BriefCards({ briefs, names }: { briefs: Brief[]; names: Record<string, string> }) {
  if (!briefs.length) return null;
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      {briefs.map((brief) => (
        <article key={brief.pillar} className="ticks flex flex-col border border-rule bg-surface p-5" aria-labelledby={`brief-${brief.pillar}`}>
          <p className="eyebrow flex items-center gap-2">
            <span className="mono inline-flex h-5 w-5 items-center justify-center rounded-[3px] bg-ink text-[10px] text-paper" aria-hidden="true">
              {PILLAR_CODE[brief.pillar]}
            </span>
            {PILLAR_LABEL[brief.pillar]}
          </p>
          <h3 id={`brief-${brief.pillar}`} className="mt-3 text-[18px] font-semibold leading-snug">
            {brief.title}
          </h3>
          <ol className="mt-4 space-y-3">
            {brief.findings.map((finding, index) => (
              <li key={index} className="grid grid-cols-[18px_1fr] gap-2 text-[13.5px] leading-relaxed">
                <span className="mono pt-0.5 text-[11px] text-muted">{index + 1}</span>
                <span>
                  {finding.text}
                  <span className="mt-1.5 flex flex-wrap gap-1">
                    {finding.citations.map((citation) => (
                      <Link
                        key={citation}
                        href={`/investigations/${citation}/`}
                        className="mono rounded-[3px] border border-rule px-1.5 py-px text-[10.5px] text-ink-2 transition-colors hover:border-ink hover:text-ink"
                      >
                        {names[citation] ?? citation} · {citation}
                      </Link>
                    ))}
                  </span>
                </span>
              </li>
            ))}
          </ol>
          <div className="mt-5 border-l-2 border-accent pl-3">
            <p className="eyebrow mb-1 text-accent">For a lunar base</p>
            <p className="text-[13.5px] leading-relaxed">{brief.implication}</p>
          </div>
          <div className="mt-4">
            <p className="eyebrow mb-1">Data gap</p>
            <p className="text-[13px] leading-relaxed text-ink-2">{brief.gap}</p>
          </div>
          <p className="mono mt-auto pt-5 text-[10.5px] text-muted">
            {brief.source === "model" ? `Drafted by ${brief.model.split("/").pop()} from NASA PSI data` : "Fact-only brief"} · {brief.review}
          </p>
        </article>
      ))}
    </div>
  );
}
