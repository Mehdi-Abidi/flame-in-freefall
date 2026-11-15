"use client";

import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { BASIS_LABEL, PHASE_COLOR, PHASE_LABEL, PILLAR_LABEL, pct, rangeText } from "@/lib/format";
import type { Investigation, Phase, Pillar } from "@/lib/types";

const PILLAR_FILTERS: (Pillar | "fundamentals")[] = ["prevention", "detection", "suppression", "fundamentals"];
const PHASE_FILTERS: Phase[] = ["solid", "liquid", "gas", "dust"];

function Chip({ on, onClick, children }: { on: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={on}
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-[4px] border px-2.5 py-1 text-[12.5px] transition-colors ${on ? "border-ink bg-ink text-paper" : "border-rule text-ink-2 hover:text-ink"}`}
    >
      {children}
    </button>
  );
}

export function InvestigationExplorer({ investigations }: { investigations: Investigation[] }) {
  const [query, setQuery] = useState("");
  const [pillar, setPillar] = useState<Pillar | "fundamentals" | null>(null);
  const [phase, setPhase] = useState<Phase | null>(null);
  const [platform, setPlatform] = useState<"flight" | "ground" | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return investigations.filter((inv) => {
      if (pillar === "fundamentals" ? inv.pillars.length > 0 : pillar && !inv.pillars.includes(pillar)) return false;
      if (phase && !inv.phases.includes(phase)) return false;
      if (platform === "ground" && inv.platform !== "ground") return false;
      if (platform === "flight" && inv.platform === "ground") return false;
      if (!q) return true;
      const haystack = [inv.name, inv.title, inv.accession, inv.summary, ...inv.fuels, ...inv.sensors].join(" ").toLowerCase();
      return haystack.includes(q);
    });
  }, [investigations, query, pillar, phase, platform]);

  const anyFilter = query || pillar || phase || platform;
  const clear = () => {
    setQuery("");
    setPillar(null);
    setPhase(null);
    setPlatform(null);
  };

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center gap-2" role="group" aria-label="Filters">
        <label className="relative">
          <span className="sr-only">Search investigations</span>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search fuel, sensor, name"
            className="mono h-8 w-56 rounded-[4px] border border-rule bg-surface px-2.5 text-[12.5px] placeholder:text-muted focus:border-ink focus:outline-none"
          />
        </label>
        <span className="mx-1 h-5 w-px bg-rule" aria-hidden="true" />
        {PILLAR_FILTERS.map((p) => (
          <Chip key={p} on={pillar === p} onClick={() => setPillar(pillar === p ? null : p)}>
            {p === "fundamentals" ? "Fundamentals" : PILLAR_LABEL[p]}
          </Chip>
        ))}
        <span className="mx-1 h-5 w-px bg-rule" aria-hidden="true" />
        {PHASE_FILTERS.map((p) => (
          <Chip key={p} on={phase === p} onClick={() => setPhase(phase === p ? null : p)}>
            <span aria-hidden="true" className="h-2 w-2 rounded-full" style={{ background: PHASE_COLOR[p] }} />
            {PHASE_LABEL[p]}
          </Chip>
        ))}
        <span className="mx-1 h-5 w-px bg-rule" aria-hidden="true" />
        <Chip on={platform === "flight"} onClick={() => setPlatform(platform === "flight" ? null : "flight")}>
          Flown
        </Chip>
        <Chip on={platform === "ground"} onClick={() => setPlatform(platform === "ground" ? null : "ground")}>
          Ground studies
        </Chip>
        <span className="mono ml-auto text-[12px] text-muted" aria-live="polite">
          {filtered.length} of {investigations.length}
          {anyFilter && (
            <button
              type="button"
              className="ml-3 text-ink-2 underline underline-offset-2 hover:text-ink"
              onClick={clear}
            >
              clear
            </button>
          )}
        </span>
      </div>

      <motion.ul layout className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <AnimatePresence initial={false}>
          {filtered.map((inv) => (
            <motion.li
              key={inv.accession}
              layout
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.98 }}
              transition={{ duration: 0.2 }}
            >
              <Link href={`/investigations/${inv.accession}/`} className="group panel flex h-full flex-col p-5 transition-transform hover:-translate-y-0.5">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="mono text-[12px] text-muted">{inv.accession}</p>
                    <p className="mt-1 text-[17px] font-semibold leading-tight">{inv.name}</p>
                  </div>
                  <span className="flex shrink-0 gap-1 pt-1" aria-label={`Fuel phases: ${inv.phases.join(", ") || "none"}`}>
                    {inv.phases.map((p) => (
                      <span key={p} className="h-2.5 w-2.5 rounded-full" style={{ background: PHASE_COLOR[p] }} title={PHASE_LABEL[p]} />
                    ))}
                  </span>
                </div>
                <p className="mt-1 line-clamp-2 text-[12.5px] text-ink-2">{inv.title}</p>
                {inv.summary && <p className="mt-3 line-clamp-3 text-[13px] leading-relaxed text-ink">{inv.summary}</p>}
                <dl className="mono mt-auto grid grid-cols-3 gap-2 border-t border-rule pt-3 text-[12px]">
                  <div>
                    <dt className="text-muted">{inv.nTests || !inv.nRecords ? "tests" : "records"}</dt>
                    <dd className="mt-0.5 text-[13px] text-ink">{inv.nTests || inv.nRecords || "none"}</dd>
                  </div>
                  <div>
                    <dt className="text-muted">O₂</dt>
                    <dd className="mt-0.5 text-[13px] text-ink">{rangeText(inv.o2Range, (v) => pct(v))}</dd>
                  </div>
                  <div>
                    <dt className="text-muted">basis</dt>
                    <dd className="mt-0.5 truncate text-[12px] text-ink-2">{inv.o2Basis ? BASIS_LABEL[inv.o2Basis] ?? inv.o2Basis : "none"}</dd>
                  </div>
                </dl>
                <div className="mt-3 flex flex-wrap gap-1">
                  {(inv.pillars.length ? inv.pillars : ["fundamentals"]).map((p) => (
                    <span key={p} className="mono rounded-[3px] border border-rule px-1.5 py-px text-[11px] uppercase tracking-[0.08em] text-ink-2">
                      {p}
                    </span>
                  ))}
                  {inv.platform === "ground" && <span className="mono rounded-[3px] border border-dashed border-rule px-1.5 py-px text-[11px] uppercase tracking-[0.08em] text-muted">ground</span>}
                </div>
              </Link>
            </motion.li>
          ))}
        </AnimatePresence>
      </motion.ul>
      {!filtered.length && (
        <div className="py-16 text-center">
          <p className="text-ink-2">{query.trim()
              ? `No investigation mentions “${query.trim()}”${pillar || phase || platform ? " with these filters" : ""}.`
              : "No investigation matches all of these filters."}</p>
          <p className="mt-1 text-[13px] text-muted">Search covers names, accession numbers, titles, summaries, fuels and sensors.</p>
          <button type="button" onClick={clear} className="mt-4 rounded-[4px] border border-rule-strong px-3 py-1.5 text-[13px] hover:border-ink">
            Clear filters
          </button>
        </div>
      )}
    </div>
  );
}
