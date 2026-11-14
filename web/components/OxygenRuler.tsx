import { PHASE_COLOR, PHASE_LABEL, pct } from "@/lib/format";
import type { PhaseOxygen, Range } from "@/lib/types";

const at = (fraction: number) => `${(fraction * 100).toFixed(2)}%`;
const exact = (fraction: number) => pct(fraction, 1).replace(".0%", "%");

export function OxygenRuler({
  phases,
  lunar,
  lunarTests,
  lunarPhases,
  earthAir = 0.21,
  spacesuit = 1,
}: {
  phases: PhaseOxygen[];
  lunar: Range;
  lunarTests: number;
  lunarPhases: string[];
  earthAir?: number;
  spacesuit?: number;
}) {
  const [lo, hi] = lunar;
  const range = (p: PhaseOxygen) => `${exact(p.min)} to ${exact(p.max)}`;
  return (
    <figure className="m-0">
      <div className="relative pl-[64px] sm:pl-[76px]">
        <div className="relative h-[34px]">
          <span className="mono absolute bottom-2 whitespace-nowrap text-[11px] text-accent" style={{ left: at(lo) }}>
            Lunar base {pct(lo)} to {pct(hi)}
          </span>
        </div>
        <div className="relative">
          <div aria-hidden="true" className="absolute inset-y-0 border-x border-dashed border-accent bg-accent-wash" style={{ left: at(lo), width: at(hi - lo) }} />
          <div aria-hidden="true" className="absolute inset-y-0 border-l border-ink-2" style={{ left: at(earthAir) }} />
          <div aria-hidden="true" className="absolute inset-y-0 border-r border-ink-2" style={{ right: 0 }} />
          {phases.map((p) => {
            const short = p.phase === "solid" && p.max < lo;
            return (
              <div key={p.phase} className={`relative border-b border-rule last:border-b-0 ${short ? "h-[74px] sm:h-[58px]" : "h-[58px]"}`}>
                <span className="absolute -left-[64px] top-[14px] text-[13px] font-medium sm:-left-[76px]">{PHASE_LABEL[p.phase]}</span>
                {short && (
                  <div
                    aria-hidden="true"
                    className="absolute top-[16px] h-[10px] rounded-r-[4px] border border-dashed border-accent"
                    style={{ left: at(p.max), width: at(hi - p.max) }}
                  />
                )}
                <div
                  aria-hidden="true"
                  className="absolute top-[16px] h-[10px] rounded-[4px]"
                  style={{ left: at(p.min), width: at(Math.max(p.max - p.min, 0.006)), background: PHASE_COLOR[p.phase] }}
                />
                <span className="mono absolute top-[31px] -ml-1 whitespace-nowrap bg-paper px-1 text-[12px] text-ink-2" style={{ left: at(p.min) }}>
                  {range(p)} · {p.count} tests
                  {short && <span className="block text-accent sm:inline"><span className="hidden sm:inline" aria-hidden="true"> · </span>none at lunar oxygen</span>}
                </span>
              </div>
            );
          })}
        </div>
        <div className="relative mt-2 h-[18px] border-t border-rule-strong">
          <span className="mono absolute top-1 hidden text-[11px] text-muted sm:block" style={{ left: 0 }}>
            0%
          </span>
          <span className="mono absolute top-1 -translate-x-1/2 whitespace-nowrap bg-paper px-1 text-[11px] text-muted" style={{ left: at(earthAir) }}>
            Earth air {pct(earthAir)}
          </span>
          <span className="mono absolute right-0 top-1 whitespace-nowrap text-[11px] text-muted">Spacesuit {pct(spacesuit)}</span>
        </div>
      </div>
      <figcaption className="mt-5 max-w-[60ch] text-[13px] leading-relaxed text-ink-2">
        Measured oxygen in every test that recorded it, by what was burning. The dashed band is a lunar base. {lunarTests} tests fall inside it on
        both oxygen and pressure, all {lunarPhases.join(" and ")} flames.
      </figcaption>
    </figure>
  );
}
