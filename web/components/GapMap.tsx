"use client";

import { Delaunay } from "d3-delaunay";
import { scaleLinear, scaleLog } from "d3-scale";
import { AnimatePresence, motion } from "motion/react";
import { Fragment, useMemo, useState } from "react";
import { HABITAT_SHORT_LABEL, PHASE_COLOR, PHASE_LABEL, PLOTTED_PHASES, pct } from "@/lib/format";
import { basisLines, oxygenMeasured, pointBasis } from "@/lib/points";
import type { Phase, Point, Scenario } from "@/lib/types";
import { useSize } from "./useSize";

interface Props {
  points: Point[];
  scenarios: Scenario[];
  names: Record<string, string>;
  selectedScenario?: string;
  highlight?: string;
  solidMaxO2?: number;
  height?: number;
  compact?: boolean;
}

const MARGIN = { top: 16, right: 18, bottom: 44, left: 56 };
const HIT_RADIUS = 24;
const TIP_WIDTH = 236;
const LABEL_BELOW = new Set(["iss"]);

interface Box {
  key: string;
  ids: string[];
  label: string;
  o2: [number, number];
  kpa: [number, number];
}

function mergeBoxes(scenarios: Scenario[]): Box[] {
  const boxes = new Map<string, Box>();
  for (const s of scenarios) {
    const key = `${s.o2.join()}|${s.kpa.join()}`;
    const label = HABITAT_SHORT_LABEL[s.id] ?? s.label;
    const existing = boxes.get(key);
    if (existing) {
      existing.ids.push(s.id);
      existing.label += ` · ${label}`;
    } else boxes.set(key, { key, ids: [s.id], label, o2: s.o2, kpa: s.kpa });
  }
  return [...boxes.values()];
}

export function GapMap({ points, scenarios, names, selectedScenario, highlight, solidMaxO2, height = 460, compact = false }: Props) {
  const { ref, width, measured } = useSize<HTMLDivElement>();
  const [phases, setPhases] = useState<Set<Phase>>(new Set(PLOTTED_PHASES));
  const [measuredOnly, setMeasuredOnly] = useState(false);
  const [view, setView] = useState<"chart" | "table">("chart");
  const [hover, setHover] = useState<Point | null>(null);

  const visible = useMemo(
    () => points.filter((p) => phases.has(p.ph) && (!measuredOnly || oxygenMeasured(p))),
    [points, phases, measuredOnly],
  );
  const active = hover && phases.has(hover.ph) && (!measuredOnly || oxygenMeasured(hover)) ? hover : null;
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const p of points) c[p.ph] = (c[p.ph] ?? 0) + 1;
    return c;
  }, [points]);

  const innerW = Math.max(width - MARGIN.left - MARGIN.right, 120);
  const innerH = height - MARGIN.top - MARGIN.bottom;
  const x = useMemo(() => scaleLinear().domain([0.1, 1]).range([0, innerW]), [innerW]);
  const y = useMemo(() => scaleLog().domain([20, 600]).rangeRound([innerH, 0]).clamp(true), [innerH]);
  const boxes = useMemo(() => mergeBoxes(scenarios), [scenarios]);

  const delaunay = useMemo(() => Delaunay.from(visible, (p) => x(p.o2), (p) => y(p.kpa)), [visible, x, y]);

  function onPoint(event: React.PointerEvent<SVGRectElement>) {
    if (!visible.length) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const mx = event.clientX - rect.left;
    const my = event.clientY - rect.top;
    const index = delaunay.find(mx, my);
    const point = visible[index];
    const distance = Math.hypot(x(point.o2) - mx, y(point.kpa) - my);
    setHover(distance <= HIT_RADIUS ? point : null);
  }

  function togglePhase(phase: Phase) {
    setPhases((current) => {
      const next = new Set(current);
      if (next.has(phase) && next.size > 1) next.delete(phase);
      else next.add(phase);
      return next;
    });
  }

  const xTicks = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1].filter((_, i) => innerW >= 420 || i % 2 === 1);
  const yTicks = compact ? [30, 100, 300] : [20, 30, 50, 70, 100, 200, 300, 500];

  const table = useMemo(() => {
    const rows = new Map<string, { a: string; n: number; o2: [number, number]; kpa: [number, number]; measured: number }>();
    for (const p of visible) {
      const row = rows.get(p.a) ?? { a: p.a, n: 0, o2: [p.o2, p.o2], kpa: [p.kpa, p.kpa], measured: 0 };
      row.n += 1;
      row.measured += oxygenMeasured(p) ? 1 : 0;
      row.o2 = [Math.min(row.o2[0], p.o2), Math.max(row.o2[1], p.o2)];
      row.kpa = [Math.min(row.kpa[0], p.kpa), Math.max(row.kpa[1], p.kpa)];
      rows.set(p.a, row);
    }
    return [...rows.values()].sort((a, b) => b.o2[1] - a.o2[1]);
  }, [visible]);

  const boxLayout = boxes.map((box) => {
    const bx = x(box.o2[0]);
    const bw = Math.max(x(box.o2[1]) - bx, 6);
    const by = y(box.kpa[1]);
    const bh = Math.max(y(box.kpa[0]) - by, 6);
    const full = box.label.toUpperCase();
    const label = bx + 4 + full.length * 7.2 > innerW && box.ids.length > 1 ? `${full.split(" · ")[0]} +${box.ids.length - 1}` : full;
    const textW = label.length * 7.2;
    const below = box.ids.some((id) => LABEL_BELOW.has(id));
    const lx = Math.max(0, Math.min(below ? bx + bw / 2 - textW / 2 : bx + 4, innerW - textW));
    const ly = below ? by + bh + 14 : by - 9;
    return { box, selected: selectedScenario ? box.ids.includes(selectedScenario) : false, bx, by, bw, bh, label, lx, ly };
  });

  const tipX = active ? MARGIN.left + x(active.o2) : 0;
  const tipY = active ? MARGIN.top + y(active.kpa) : 0;

  return (
    <figure className="m-0">
      <div className="mb-3 flex flex-wrap items-center gap-2" role="group" aria-label="Chart filters">
        {PLOTTED_PHASES.map((phase) => {
          const on = phases.has(phase);
          return (
            <button
              key={phase}
              type="button"
              aria-pressed={on}
              onClick={() => togglePhase(phase)}
              className={`inline-flex items-center gap-2 rounded-[4px] border px-2.5 py-1 text-[12.5px] transition-colors ${on ? "border-rule-strong bg-surface text-ink" : "border-rule text-muted"}`}
            >
              <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full" style={{ background: on ? PHASE_COLOR[phase] : "transparent", boxShadow: `inset 0 0 0 1.5px ${PHASE_COLOR[phase]}` }} />
              {PHASE_LABEL[phase]}
              <span className="mono text-[12px] text-muted">{counts[phase] ?? 0}</span>
            </button>
          );
        })}
        <span className="mx-1 h-5 w-px bg-rule" aria-hidden="true" />
        <button
          type="button"
          aria-pressed={measuredOnly}
          onClick={() => setMeasuredOnly((v) => !v)}
          className={`inline-flex items-center gap-2 rounded-[4px] border px-2.5 py-1 text-[12.5px] transition-colors ${measuredOnly ? "border-rule-strong bg-surface text-ink" : "border-rule text-ink-2"}`}
        >
          <span aria-hidden="true" className="inline-flex gap-0.5">
            <span className="h-2.5 w-2.5 rounded-full bg-ink-2" />
            <span className="grid h-2.5 w-2.5 place-items-center rounded-full border-[1.5px] border-ink-2">
              <span className="h-[3px] w-[3px] rounded-full bg-ink-2" />
            </span>
            {!measuredOnly && <span className="h-2.5 w-2.5 rounded-full border-[1.5px] border-ink-2" />}
          </span>
          {measuredOnly ? "Measured oxygen only" : "Measured and assumed"}
        </button>
        <div className="ml-auto inline-flex rounded-[4px] border border-rule p-0.5" role="group" aria-label="View">
          {(["chart", "table"] as const).map((v) => (
            <button
              key={v}
              type="button"
              aria-pressed={view === v}
              onClick={() => {
                setView(v);
                setHover(null);
              }}
              className={`mono rounded-[3px] px-2.5 py-1 text-[12px] uppercase tracking-[0.1em] ${view === v ? "bg-ink text-paper" : "text-ink-2"}`}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      <div ref={ref} className="relative w-full min-w-0 overflow-hidden">
        {view === "chart" && !measured ? (
          <div style={{ height }} aria-hidden="true" />
        ) : view === "chart" ? (
          <svg width={width} height={height} role="img" aria-label={`Scatter of ${visible.length} tests: oxygen fraction against pressure, with habitat target boxes`} className="block select-none">
            <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
              {yTicks.map((t) => (
                <g key={`y${t}`} transform={`translate(0,${y(t)})`}>
                  <line x2={innerW} stroke="var(--rule)" strokeWidth={1} />
                  <text x={-10} dy="0.32em" textAnchor="end" className="mono" fontSize={11} fill="var(--muted)">
                    {t}
                  </text>
                </g>
              ))}
              {xTicks.map((t) => (
                <g key={`x${t}`} transform={`translate(${x(t)},${innerH})`}>
                  <line y2={5} stroke="var(--rule-strong)" />
                  <text y={18} textAnchor="middle" className="mono" fontSize={11} fill="var(--muted)">
                    {pct(t)}
                  </text>
                </g>
              ))}
              <line y1={innerH} y2={innerH} x2={innerW} stroke="var(--rule-strong)" />
              <text x={innerW} y={innerH + 36} textAnchor="end" fontSize={12} fill="var(--ink-2)">
                Oxygen in the atmosphere (% by volume)
              </text>
              <text transform={`translate(${-44},${innerH / 2}) rotate(-90)`} textAnchor="middle" fontSize={12} fill="var(--ink-2)">
                Pressure (kPa, log scale)
              </text>

              {boxLayout.map(({ box, selected, bx, by, bw, bh }) => (
                <motion.rect
                  key={box.key}
                  initial={false}
                  animate={{ x: bx, y: by, width: bw, height: bh }}
                  transition={{ type: "spring", stiffness: 220, damping: 30 }}
                  fill={selected ? "var(--accent-wash)" : "var(--target-wash)"}
                  stroke={selected ? "var(--accent)" : "var(--ink-2)"}
                  strokeWidth={selected ? 1.5 : 1}
                  rx={2}
                />
              ))}

              {solidMaxO2 !== undefined && phases.has("solid") && (
                <line x1={x(solidMaxO2)} x2={x(solidMaxO2)} y1={0} y2={innerH} stroke="var(--s1)" strokeWidth={1} opacity={0.7} />
              )}

              <g>
                {visible.map((p, index) => {
                  const opacity = highlight && p.a !== highlight ? 0.12 : 0.88;
                  const transition = { duration: 0.4, delay: Math.min(index * 0.0006, 0.5) };
                  const basis = pointBasis(p);
                  return (
                    <Fragment key={p.id}>
                      <motion.circle
                        cx={x(p.o2)}
                        cy={y(p.kpa)}
                        r={4}
                        initial={{ opacity: 0, scale: 0.4 }}
                        animate={{ opacity, scale: 1 }}
                        transition={transition}
                        fill={basis === "measured" ? PHASE_COLOR[p.ph] : "var(--surface)"}
                        stroke={basis === "measured" ? "var(--surface)" : PHASE_COLOR[p.ph]}
                        strokeWidth={1.5}
                      />
                      {basis === "oxygen" && (
                        <motion.circle
                          cx={x(p.o2)}
                          cy={y(p.kpa)}
                          r={1.6}
                          initial={{ opacity: 0, scale: 0.4 }}
                          animate={{ opacity, scale: 1 }}
                          transition={transition}
                          fill={PHASE_COLOR[p.ph]}
                        />
                      )}
                    </Fragment>
                  );
                })}
              </g>

              {!compact &&
                boxLayout.map(({ box, selected, label, lx, ly }) => (
                  <text key={box.key} x={lx} y={ly} fontSize={12} className="mono" fill={selected ? "var(--accent)" : "var(--ink-2)"} stroke="var(--surface)" strokeWidth={4} paintOrder="stroke" strokeLinejoin="round">
                    {label}
                  </text>
                ))}
              {!compact && solidMaxO2 !== undefined && phases.has("solid") && (
                <text x={x(solidMaxO2) + 6} y={14} fontSize={12} fill="var(--ink)" stroke="var(--surface)" strokeWidth={4} paintOrder="stroke" strokeLinejoin="round">
                  <tspan fontWeight={600}>Solid materials stop here</tspan>
                  <tspan x={x(solidMaxO2) + 6} dy={14} fill="var(--ink-2)">
                    highest measured: {pct(solidMaxO2, 1)} O₂
                  </tspan>
                </text>
              )}

              {active && (
                <circle cx={x(active.o2)} cy={y(active.kpa)} r={8} fill="none" stroke="var(--ink)" strokeWidth={1.5} pointerEvents="none" />
              )}

              <rect
                width={innerW}
                height={innerH}
                fill="transparent"
                onPointerMove={(event) => {
                  if (event.pointerType === "mouse") onPoint(event);
                }}
                onPointerUp={(event) => {
                  if (event.pointerType !== "mouse") onPoint(event);
                }}
                onPointerLeave={(event) => {
                  if (event.pointerType === "mouse") setHover(null);
                }}
              />
            </g>
          </svg>
        ) : (
          <div className="max-h-[460px] overflow-auto rounded-[4px] border border-rule">
            <table className="w-full border-collapse text-[13px]">
              <caption className="sr-only">Tests per investigation shown on the chart</caption>
              <thead className="sticky top-0 bg-surface-2 text-left">
                <tr className="eyebrow">
                  <th className="px-3 py-2 font-normal">Investigation</th>
                  <th className="px-3 py-2 text-right font-normal">Tests</th>
                  <th className="px-3 py-2 text-right font-normal">O₂ measured</th>
                  <th className="px-3 py-2 text-right font-normal">O₂ range</th>
                  <th className="px-3 py-2 text-right font-normal">Pressure range</th>
                </tr>
              </thead>
              <tbody>
                {table.map((row) => (
                  <tr key={row.a} className="border-t border-rule">
                    <td className="px-3 py-2">{names[row.a] ?? row.a}</td>
                    <td className="mono px-3 py-2 text-right">{row.n}</td>
                    <td className="mono px-3 py-2 text-right">{row.measured}</td>
                    <td className="mono px-3 py-2 text-right">{pct(row.o2[0])} to {pct(row.o2[1])}</td>
                    <td className="mono px-3 py-2 text-right">{Math.round(row.kpa[0])} to {Math.round(row.kpa[1])} kPa</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <AnimatePresence>
          {view === "chart" && active && (
            <motion.div
              key="tip"
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.12 }}
              className="pointer-events-none absolute z-10 w-max rounded-[4px] border border-rule bg-surface px-3 py-2 text-[12px] shadow-lg"
              style={{
                maxWidth: TIP_WIDTH,
                left: Math.max(4, Math.min(tipX + 14, width - TIP_WIDTH - 4)),
                ...(tipY > 108 ? { bottom: height - tipY + 12 } : { top: tipY + 14 }),
              }}
            >
              <div className="mono text-[13px] font-medium text-ink">
                {pct(active.o2, 1)} O₂ · {Math.round(active.kpa)} kPa
              </div>
              <div className="mt-0.5 flex items-center gap-1.5 text-ink-2">
                <span className="inline-block h-[2px] w-3 shrink-0" style={{ background: PHASE_COLOR[active.ph] }} />
                {names[active.a] ?? active.a} · {active.fuel}
              </div>
              {basisLines(active).map((line) => (
                <div key={line} className="mt-0.5 text-[12px] text-muted">
                  {line}
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
      {!compact && (
        <figcaption className="mt-3 text-[12px] text-muted">
          Each dot is one test from a NASA PSI experimental table. Filled: oxygen and pressure both measured. Ring with a centre: oxygen measured,
          pressure assumed. Hollow: assumed cabin air or a planned test matrix. Boxes are habitat targets from the challenge text.{" "}
          {visible.length.toLocaleString("en-US")} tests shown.
        </figcaption>
      )}
    </figure>
  );
}
