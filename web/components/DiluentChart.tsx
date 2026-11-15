import type { DiluentRow } from "@/lib/flex";

const AXIS = { lo: 0.1, hi: 0.36 };
const at = (fraction: number) => ((fraction - AXIS.lo) / (AXIS.hi - AXIS.lo)) * 100;
const share = (fraction: number) => `${Number((fraction * 100).toFixed(1))}%`;

/** FLEX side by side: for each diluent, how many droplet tests went out and across which oxygen levels. */
export function DiluentChart({ rows }: { rows: DiluentRow[] }) {
  if (!rows.length) return null;
  return (
    <figure className="panel m-0 p-5 sm:p-6">
      <figcaption>
        <p className="eyebrow">FLEX · PSI-69</p>
        <h3 className="display mt-2 text-[28px]">How droplet flames went out, by diluent</h3>
      </figcaption>
      <div className="mt-6 space-y-5">
        {rows.map((row) => (
          <div key={row.diluent}>
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 text-[15px]">
              <span className="font-medium">{row.label}</span>
              <span className="mono text-[12.5px] text-ink-2">
                {row.out} of {row.tests} tests went out
              </span>
            </div>
            <div className="relative mt-2 h-3 bg-surface-2">
              <div className="absolute inset-y-0 bg-ice" style={{ left: `${at(row.lo)}%`, width: `${at(row.hi) - at(row.lo)}%` }} />
            </div>
            <p className="mono mt-1.5 text-[11.5px] text-muted">
              extinction recorded from {share(row.lo)} to {share(row.hi)} oxygen
            </p>
          </div>
        ))}
      </div>
      <div className="mono mt-4 flex justify-between border-t border-rule pt-2 text-[11px] text-muted">
        <span>{share(AXIS.lo)} oxygen</span>
        <span>{share(AXIS.hi)}</span>
      </div>
      <p className="mt-4 max-w-[62ch] text-[13px] leading-relaxed text-ink-2">Each diluent was flown over a different set of tests, so this shows what happened. It does not rank the agents.</p>
    </figure>
  );
}
