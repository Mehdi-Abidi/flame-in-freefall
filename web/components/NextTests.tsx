import Link from "next/link";
import type { NextTest } from "@/lib/nextTests";

export function NextTests({ tests, names }: { tests: NextTest[]; names: Record<string, string> }) {
  if (!tests.length) return null;
  return (
    <ol className="grid gap-4 md:grid-cols-2">
      {tests.map((test) => (
        <li key={test.id} className="panel flex flex-col p-5">
          <h3 className="display text-[28px]">{test.title}</h3>
          <p className="mt-3 max-w-[60ch] text-[14px] leading-relaxed text-ink-2">{test.evidence}</p>
          <div className="mt-4 max-w-[60ch] border-l-2 border-accent pl-3">
            <p className="text-[13px] font-medium text-accent">Proposed test</p>
            <p className="mt-1 text-[14px] leading-relaxed">{test.proposal}</p>
          </div>
          <p className="mt-4 flex flex-wrap items-center gap-1 text-[12px] text-muted">
            <span className="mr-1">Builds on</span>
            {test.buildsOn.map((accession) => (
              <Link
                key={accession}
                href={`/investigations/${accession}/`}
                className="mono rounded-[3px] border border-rule px-1.5 py-px text-[12px] text-ink-2 transition-colors hover:border-ink hover:text-ink"
              >
                {names[accession] ?? accession} · {accession}
              </Link>
            ))}
          </p>
        </li>
      ))}
    </ol>
  );
}
