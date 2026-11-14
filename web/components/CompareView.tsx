"use client";

import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { BASIS_LABEL, PHASE_LABEL, pct, rangeText } from "@/lib/format";
import type { Investigation } from "@/lib/types";

const MAX = 4;
const DEFAULT_IDS = ["PSI-69", "PSI-68"];

interface Row {
  label: string;
  value: (inv: Investigation) => string;
}

const join = (items: string[]) => (items.length ? items.join(", ") : "not stated");
const basis = (b: string | null) => (b ? ` (${BASIS_LABEL[b] ?? b})` : "");

const ROWS: Row[] = [
  { label: "Platform", value: (i) => i.platform ?? "not stated" },
  { label: "Hardware", value: (i) => i.hardware ?? "not stated" },
  { label: "Fire-safety pillars", value: (i) => join(i.pillars) || "fundamentals" },
  { label: "Fuel phase", value: (i) => join(i.phases.map((p) => PHASE_LABEL[p])) },
  { label: "Fuels and materials", value: (i) => join(i.fuels) },
  { label: "Sample geometry", value: (i) => join(i.geometry) },
  { label: "Sample size", value: (i) => i.sampleSize ?? "not stated" },
  { label: "Oxygen", value: (i) => rangeText(i.o2Range, (v) => pct(v, 1)) + basis(i.o2Basis) },
  { label: "Pressure", value: (i) => rangeText(i.kpaRange, (v) => `${Math.round(v)} kPa`) + basis(i.kpaBasis) },
  { label: "Varied between tests", value: (i) => join(i.varied) },
  { label: "Held fixed", value: (i) => join(i.fixed) },
  { label: "Sensors", value: (i) => join(i.sensors) },
  { label: "Tests", value: (i) => (i.nTests ? String(i.nTests) : `${i.nRecords} records, no per-test rows`) },
  { label: "Lunar base rank", value: (i) => (i.scores.lunar_base ? `#${i.scores.lunar_base.rank} · ${Math.round(i.scores.lunar_base.score * 100)}` : "n/a") },
  { label: "ISS rank", value: (i) => (i.scores.iss ? `#${i.scores.iss.rank} · ${Math.round(i.scores.iss.score * 100)}` : "n/a") },
  { label: "Publications", value: (i) => String(i.publications.length) },
];

export function CompareView({ investigations }: { investigations: Investigation[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const [onlyDiff, setOnlyDiff] = useState(false);
  const byId = useMemo(() => new Map(investigations.map((i) => [i.accession, i])), [investigations]);

  const requested = (params.get("ids") ?? "").split(",").filter((id) => byId.has(id));
  const ids = (requested.length ? requested : DEFAULT_IDS).slice(0, MAX);
  const selected = ids.map((id) => byId.get(id)).filter((i): i is Investigation => Boolean(i));

  function setIds(next: string[]) {
    const query = new URLSearchParams(params.toString());
    query.set("ids", next.join(","));
    router.replace(`${pathname}?${query.toString()}`, { scroll: false });
  }

  function toggle(id: string) {
    if (ids.includes(id)) setIds(ids.filter((x) => x !== id));
    else if (ids.length < MAX) setIds([...ids, id]);
  }

  const rows = ROWS.map((row) => {
    const values = selected.map(row.value);
    return { ...row, values, differs: new Set(values).size > 1 };
  });
  const shown = onlyDiff ? rows.filter((r) => r.differs) : rows;
  const diffCount = rows.filter((r) => r.differs).length;

  return (
    <div>
      <div className="panel mb-6 p-4">
        <div className="mb-3 flex items-baseline justify-between">
          <p className="eyebrow">Choose up to {MAX}</p>
          <p className="mono text-[11px] text-muted">{selected.length} selected</p>
        </div>
        <ul className="flex flex-wrap gap-1.5">
          {investigations.map((inv) => {
            const on = ids.includes(inv.accession);
            const disabled = !on && ids.length >= MAX;
            return (
              <li key={inv.accession}>
                <button
                  type="button"
                  aria-pressed={on}
                  disabled={disabled}
                  onClick={() => toggle(inv.accession)}
                  className={`rounded-[4px] border px-2.5 py-1 text-[12.5px] transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${on ? "border-ink bg-ink text-paper" : "border-rule text-ink-2 hover:text-ink"}`}
                >
                  {inv.name}
                </button>
              </li>
            );
          })}
        </ul>
      </div>

      {selected.length < 2 ? (
        <p className="py-12 text-center text-ink-2">Pick at least two investigations to compare.</p>
      ) : (
        <>
          <div className="mb-3 flex items-center justify-between">
            <p className="text-[13px] text-ink-2">
              <span className="font-semibold text-ink">{diffCount}</span> of {rows.length} attributes differ
            </p>
            <button
              type="button"
              aria-pressed={onlyDiff}
              onClick={() => setOnlyDiff((v) => !v)}
              className={`rounded-[4px] border px-2.5 py-1 text-[12.5px] ${onlyDiff ? "border-ink bg-ink text-paper" : "border-rule text-ink-2"}`}
            >
              Only differences
            </button>
          </div>
          <div className="overflow-x-auto rounded-[6px] border border-rule bg-surface">
            <table className="w-full min-w-[720px] border-collapse text-[13px]">
              <thead>
                <tr className="border-b border-rule-strong">
                  <th className="w-[180px] px-4 py-3 text-left">
                    <span className="eyebrow">Attribute</span>
                  </th>
                  {selected.map((inv) => (
                    <th key={inv.accession} className="px-4 py-3 text-left align-bottom">
                      <Link href={`/investigations/${inv.accession}/`} className="group">
                        <span className="mono block text-[10.5px] font-normal text-muted">{inv.accession}</span>
                        <span className="block text-[16px] font-semibold group-hover:underline">{inv.name}</span>
                      </Link>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <AnimatePresence initial={false}>
                  {shown.map((row) => (
                    <motion.tr
                      key={row.label}
                      layout
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="border-b border-rule last:border-0"
                    >
                      <th scope="row" className="px-4 py-2.5 text-left align-top font-normal">
                        <span className="flex items-center gap-2 text-ink-2">
                          {row.differs ? (
                            <span className="mono rounded-[2px] bg-accent px-1 text-[9px] uppercase tracking-[0.08em] text-accent-ink">diff</span>
                          ) : (
                            <span className="mono rounded-[2px] border border-rule px-1 text-[9px] uppercase tracking-[0.08em] text-muted">same</span>
                          )}
                          {row.label}
                        </span>
                      </th>
                      {row.values.map((value, index) => (
                        <td key={selected[index].accession} className={`px-4 py-2.5 align-top leading-relaxed ${row.differs ? "text-ink" : "text-ink-2"}`}>
                          {value}
                        </td>
                      ))}
                    </motion.tr>
                  ))}
                </AnimatePresence>
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
