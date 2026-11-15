"use client";

import * as Slider from "@radix-ui/react-slider";
import * as ToggleGroup from "@radix-ui/react-toggle-group";
import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { BASIS_LABEL, HABITAT_SHORT_LABEL, PILLAR_LABEL, pct } from "@/lib/format";
import { COMPONENT_ORDER, DEFAULT_WEIGHTS, MAX_WEIGHT, PILLARS, rankFor, sanitizeWeights } from "@/lib/rank";
import type { Components, Investigation, Scenario, Weights } from "@/lib/types";

const COMPONENT_META: Record<keyof Components, { label: string; color: string; help: string }> = {
  condition_fit: { label: "Condition fit", color: "var(--s1)", help: "How close its tests came to this habitat's oxygen and pressure" },
  pillar_match: { label: "Pillar match", color: "var(--s2)", help: "Whether it covers the fire-safety pillar you weight most" },
  material_relevance: { label: "Material", color: "var(--s3)", help: "Solids count most, then liquids, gases and dust" },
  data_richness: { label: "Data richness", color: "var(--s4)", help: "Tests, files and publications, log-scaled" },
};

const PRESETS: { label: string; weights: Weights }[] = [
  { label: "Balanced", weights: { prevention: 1, detection: 1, suppression: 1 } },
  { label: "Prevention first", weights: { prevention: 3, detection: 0.5, suppression: 0.5 } },
  { label: "Detection first", weights: { prevention: 0.5, detection: 3, suppression: 0.5 } },
  { label: "Suppression first", weights: { prevention: 0.5, detection: 0.5, suppression: 3 } },
];

function parseWeights(text: string | null): Weights {
  if (!text) return { ...DEFAULT_WEIGHTS };
  const [prevention, detection, suppression] = text.split(",").map(Number);
  return sanitizeWeights({ prevention, detection, suppression });
}

interface Props {
  investigations: Investigation[];
  scenarios: Scenario[];
  componentWeights: Components;
}

export function RankBoard({ investigations, scenarios, componentWeights }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const scenarioIds = scenarios.map((s) => s.id);
  const requested = params.get("habitat");
  const scenarioId = requested && scenarioIds.includes(requested) ? requested : "lunar_base";
  const weights = parseWeights(params.get("weights"));
  const [open, setOpen] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);

  const scenario = scenarios.find((s) => s.id === scenarioId) ?? scenarios[0];
  const rows = useMemo(() => rankFor(investigations, scenario.id, componentWeights, weights), [investigations, scenario.id, componentWeights, weights]);
  const baseline = useMemo(() => {
    const map = new Map<string, number>();
    for (const row of rankFor(investigations, scenario.id, componentWeights, DEFAULT_WEIGHTS)) map.set(row.investigation.accession, row.rank);
    return map;
  }, [investigations, scenario.id, componentWeights]);
  const visible = showAll ? rows : rows.slice(0, 12);

  function update(next: { habitat?: string; weights?: Weights }) {
    const query = new URLSearchParams(params.toString());
    if (next.habitat) query.set("habitat", next.habitat);
    if (next.weights) {
      const w = next.weights;
      const isDefault = PILLARS.every((p) => w[p] === DEFAULT_WEIGHTS[p]);
      if (isDefault) query.delete("weights");
      else query.set("weights", PILLARS.map((p) => w[p]).join(","));
    }
    router.replace(`${pathname}?${query.toString()}`, { scroll: false });
  }

  const sharePercent = (key: keyof Components) => Math.round(componentWeights[key] * 100);

  return (
    <div className="grid gap-8 lg:grid-cols-[320px_1fr]">
      <aside className="lg:sticky lg:top-24 lg:self-start">
        <div className="panel p-5">
          <p className="eyebrow mb-3">Habitat</p>
          <ToggleGroup.Root
            type="single"
            value={scenario.id}
            onValueChange={(value) => value && update({ habitat: value })}
            aria-label="Habitat"
            className="grid grid-cols-3 gap-1.5"
          >
            {scenarios.map((s) => (
              <ToggleGroup.Item
                key={s.id}
                value={s.id}
                className="rounded-[4px] border border-rule px-2 py-2 text-[12.5px] text-ink-2 transition-colors hover:border-rule-strong hover:text-ink data-[state=on]:border-ink data-[state=on]:bg-ink data-[state=on]:text-paper"
              >
                {HABITAT_SHORT_LABEL[s.id] ?? s.label}
              </ToggleGroup.Item>
            ))}
          </ToggleGroup.Root>

          <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-rule pt-4">
            <div>
              <dt className="eyebrow">Oxygen</dt>
              <dd className="mono mt-1 text-[15px]">
                {pct(scenario.o2[0])} to {pct(scenario.o2[1])}
              </dd>
            </div>
            <div>
              <dt className="eyebrow">Pressure</dt>
              <dd className="mono mt-1 text-[15px]">
                {scenario.kpa[0]} to {scenario.kpa[1]} kPa
              </dd>
            </div>
          </dl>
          <p className="mt-3 text-[12.5px] leading-relaxed text-ink-2">{scenario.source}</p>
          {scenario.assumptions.map((a) => (
            <p key={a} className="mt-2 border-l-2 border-accent pl-2.5 text-[12px] leading-relaxed text-ink-2">
              <span className="mono mr-1 text-[11px] uppercase tracking-[0.1em] text-accent">Assumption</span>
              {a}
            </p>
          ))}
        </div>

        <div className="panel mt-4 p-5">
          <div className="mb-3 flex items-baseline justify-between">
            <p className="eyebrow">Fire-safety priorities</p>
            <button type="button" onClick={() => update({ weights: { ...DEFAULT_WEIGHTS } })} className="mono text-[12px] text-ink-2 underline-offset-2 hover:text-ink hover:underline">
              reset
            </button>
          </div>
          <div className="space-y-5">
            {PILLARS.map((pillar) => (
              <div key={pillar}>
                <div className="mb-2 flex items-baseline justify-between">
                  <label id={`w-${pillar}`} className="text-[13.5px]">
                    {PILLAR_LABEL[pillar]}
                  </label>
                  <span className="mono text-[12px] text-ink-2">×{weights[pillar].toFixed(1)}</span>
                </div>
                <Slider.Root
                  value={[weights[pillar]]}
                  min={0}
                  max={MAX_WEIGHT}
                  step={0.5}
                  onValueChange={([value]) => update({ weights: { ...weights, [pillar]: value } })}
                  aria-labelledby={`w-${pillar}`}
                  className="relative flex h-5 touch-none select-none items-center"
                >
                  <Slider.Track className="relative h-[3px] grow rounded-full bg-rule">
                    <Slider.Range className="absolute h-full rounded-full bg-ink" />
                  </Slider.Track>
                  <Slider.Thumb className="block h-4 w-4 rounded-full border-2 border-ink bg-surface shadow transition-transform hover:scale-110 focus-visible:scale-110" aria-label={`${PILLAR_LABEL[pillar]} weight`} />
                </Slider.Root>
              </div>
            ))}
          </div>
          <div className="mt-5 flex flex-wrap gap-1.5 border-t border-rule pt-4">
            {PRESETS.map((preset) => {
              const on = PILLARS.every((p) => preset.weights[p] === weights[p]);
              return (
                <button
                  key={preset.label}
                  type="button"
                  aria-pressed={on}
                  onClick={() => update({ weights: preset.weights })}
                  className={`rounded-[4px] border px-2 py-1 text-[12px] transition-colors ${on ? "border-accent text-accent" : "border-rule text-ink-2 hover:text-ink"}`}
                >
                  {preset.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="panel mt-4 p-5">
          <p className="eyebrow mb-3">How a score is built</p>
          <ul className="space-y-2.5">
            {COMPONENT_ORDER.map((key) => (
              <li key={key} className="flex gap-2.5 text-[12.5px]">
                <span aria-hidden="true" className="mt-1 h-2.5 w-2.5 shrink-0 rounded-[2px]" style={{ background: COMPONENT_META[key].color }} />
                <span>
                  <span className="font-medium">{COMPONENT_META[key].label}</span>
                  <span className="mono text-muted"> · {sharePercent(key)}%</span>
                  <span className="block text-ink-2">{COMPONENT_META[key].help}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <section aria-label={`Ranking for ${scenario.label}`}>
        <div className="mb-3 flex items-end justify-between gap-4">
          <div>
            <p className="eyebrow">Ranking · {scenario.label}</p>
            {scenario.contextOnly && (
              <p className="mt-2 max-w-xl text-[13px] text-ink-2">
                Context only: no NASA test comes near spacesuit conditions, so this ranking mostly reflects material, pillar and data. That gap is the finding.
              </p>
            )}
          </div>
          <p className="mono shrink-0 text-[12px] text-muted">{rows.length} investigations</p>
        </div>

        <LayoutGroup>
          <ol className="space-y-2">
            <AnimatePresence initial={false}>
              {visible.map((row) => {
                const inv = row.investigation;
                const delta = (baseline.get(inv.accession) ?? row.rank) - row.rank;
                const expanded = open === inv.accession;
                const evidence = inv.scores[scenario.id]?.evidence;
                const reasons = inv.scores[scenario.id]?.reasons ?? [];
                const rationale = inv.scores[scenario.id]?.rationale ?? null;
                return (
                  <motion.li
                    key={inv.accession}
                    layout="position"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ type: "spring", stiffness: 380, damping: 34 }}
                    className={`panel overflow-hidden ${row.rank <= 3 ? "border-rule-strong" : ""}`}
                  >
                    <button
                      type="button"
                      onClick={() => setOpen(expanded ? null : inv.accession)}
                      aria-expanded={expanded}
                      className="grid w-full grid-cols-[44px_1fr_auto] items-center gap-3 px-4 py-3 text-left sm:grid-cols-[52px_1fr_minmax(160px,34%)_64px] sm:gap-4"
                    >
                      <span className="mono text-[22px] font-medium leading-none text-ink">
                        {String(row.rank).padStart(2, "0")}
                        {delta !== 0 && (
                          <span className={`mono ml-1 align-top text-[11px] ${delta > 0 ? "text-[color:var(--good)]" : "text-muted"}`} aria-label={delta > 0 ? `up ${delta}` : `down ${-delta}`}>
                            {delta > 0 ? `▲${delta}` : `▼${-delta}`}
                          </span>
                        )}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-[15px] font-medium">{inv.name}</span>
                        <span className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12px] text-ink-2">
                          <span className="truncate">{inv.title}</span>
                        </span>
                        <span className="mt-1.5 flex flex-wrap gap-1">
                          {inv.pillars.length ? (
                            inv.pillars.map((p) => (
                              <span key={p} className={`mono rounded-[3px] border px-1.5 py-px text-[11px] uppercase tracking-[0.08em] ${weights[p] === Math.max(...PILLARS.map((x) => weights[x])) ? "border-ink text-ink" : "border-rule text-muted"}`}>
                                {p}
                              </span>
                            ))
                          ) : (
                            <span className="mono rounded-[3px] border border-dashed border-rule px-1.5 py-px text-[11px] uppercase tracking-[0.08em] text-muted">fundamentals</span>
                          )}
                        </span>
                      </span>
                      <span className="hidden sm:block" aria-hidden="true">
                        <span className="flex h-2 w-full gap-[2px]">
                          {COMPONENT_ORDER.map((key) => (
                            <motion.span
                              key={key}
                              layout
                              className="h-full first:rounded-l-full last:rounded-r-full"
                              style={{ background: COMPONENT_META[key].color, width: `${row.contributions[key] * 100}%` }}
                              title={`${COMPONENT_META[key].label}: ${row.components[key].toFixed(2)}`}
                            />
                          ))}
                        </span>
                      </span>
                      <span className="text-right">
                        <span className="block text-[20px] font-semibold leading-none">{Math.round(row.score * 100)}</span>
                        <span className="mono text-[11px] text-muted">/ 100</span>
                      </span>
                    </button>
                    <AnimatePresence initial={false}>
                      {expanded && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.25, ease: [0.2, 0.8, 0.2, 1] }}
                          className="border-t border-rule"
                        >
                          <div className="grid gap-5 px-4 py-4 md:grid-cols-[1.2fr_1fr]">
                            <div>
                              <p className="eyebrow mb-2">Why it ranks here</p>
                              {rationale && (
                                <figure className="mb-3 border-l-2 border-ink pl-3">
                                  <blockquote className="text-[14.5px] leading-relaxed">{rationale.text}</blockquote>
                                  <figcaption className="mono mt-1.5 text-[11px] text-muted">
                                    {rationale.source === "model" ? `Written by ${rationale.model.split("/").pop()} from the score parts` : "Fact-only template"} · for balanced priorities
                                  </figcaption>
                                </figure>
                              )}
                              <ul className="space-y-1.5 text-[13.5px] leading-relaxed">
                                {reasons.map((r) => (
                                  <li key={r} className="flex gap-2">
                                    <span aria-hidden="true" className="mt-2 h-1 w-1 shrink-0 rounded-full bg-ink-2" />
                                    {r}
                                  </li>
                                ))}
                              </ul>
                              {inv.summary && <p className="mt-3 text-[13px] leading-relaxed text-ink-2">{inv.summary}</p>}
                              <Link href={`/investigations/${inv.accession}/`} className="link-underline mt-3 inline-block text-[13px] font-medium text-accent">
                                Open {inv.name} →
                              </Link>
                            </div>
                            <div>
                              <p className="eyebrow mb-2">Score parts</p>
                              <table className="w-full text-[12.5px]">
                                <tbody>
                                  {COMPONENT_ORDER.map((key) => (
                                    <tr key={key} className="border-b border-rule last:border-0">
                                      <td className="py-1.5">
                                        <span aria-hidden="true" className="mr-2 inline-block h-2 w-2 rounded-[2px]" style={{ background: COMPONENT_META[key].color }} />
                                        {COMPONENT_META[key].label}
                                      </td>
                                      <td className="mono py-1.5 text-right">{row.components[key].toFixed(2)}</td>
                                      <td className="mono py-1.5 text-right text-muted">+{(row.contributions[key] * 100).toFixed(1)}</td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                              {evidence && (
                                <p className="mono mt-3 text-[12px] leading-relaxed text-ink-2">
                                  {evidence.n_considered} tests compared · {evidence.n_in_target} inside target · {evidence.n_near} near
                                  {inv.o2Basis && inv.o2Basis !== "measured" ? ` · O₂ ${BASIS_LABEL[inv.o2Basis] ?? inv.o2Basis}` : ""}
                                </p>
                              )}
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.li>
                );
              })}
            </AnimatePresence>
          </ol>
        </LayoutGroup>
        {rows.length > 12 && (
          <button type="button" onClick={() => setShowAll((v) => !v)} className="mt-4 w-full rounded-[4px] border border-dashed border-rule-strong py-2.5 text-[13px] text-ink-2 hover:text-ink">
            {showAll ? "Show top 12" : `Show all ${rows.length}`}
          </button>
        )}
      </section>
    </div>
  );
}
