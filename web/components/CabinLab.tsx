"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import * as Slider from "@radix-ui/react-slider";
import * as ToggleGroup from "@radix-ui/react-toggle-group";
import { motion } from "motion/react";
import { HABITAT_SHORT_LABEL, PHASE_COLOR } from "@/lib/format";
import { burnExtent } from "@/lib/gravity";
import { GRAVITIES, LAB_PHASES, TOLERANCE, breathing, flamePath, presetFor, readCabin, richer, type GravityId, type LabTest, type Reading, type Verdict } from "@/lib/lab";
import type { GravityRow, Phase, Scenario } from "@/lib/types";

interface Props {
  tests: LabTest[];
  smoke: { tests: number; o2: number; accessions: string[] };
  scenarios: Scenario[];
  names: Record<string, string>;
  groundRow: GravityRow | null;
}

const PHASE_COPY: Record<string, { label: string; things: string }> = {
  solid: { label: "Solid", things: "Fabrics, plastics" },
  liquid: { label: "Liquid", things: "Fuel droplets" },
  gas: { label: "Gas", things: "Gas flames" },
};

const VERDICT: Record<Verdict, { word: string; color: string; fill: number }> = {
  flown: { word: "Flown", color: "var(--good)", fill: 0.92 },
  thin: { word: "Barely flown", color: "var(--warn-ink)", fill: 0.5 },
  never: { word: "Never flown", color: "var(--accent)", fill: 0.1 },
};

const HABITAT_GRAVITY: Record<string, GravityId> = { lunar_base: "moon", pressurized_rover: "moon", mars_habitat: "mars" };
const O2_SCALE = { min: 10, max: 100 };
const KPA_SCALE = { min: 20, max: 105 };
const CHIP =
  "rounded-[4px] border border-rule px-2 py-2 text-[12.5px] text-ink-2 transition-[color,border-color,transform] hover:border-rule-strong hover:text-ink active:translate-y-px data-[state=on]:border-ink data-[state=on]:bg-ink data-[state=on]:text-paper";

const share = (fraction: number) => `${Number((fraction * 100).toFixed(1))}%`;
const points = (fraction: number) => `${Number((fraction * 100).toFixed(1))} points`;
const plural = (n: number, one: string, many: string) => (n === 1 ? one : many);

function gravityLine(id: GravityId, row: GravityRow | null): string {
  if (id === "orbit") return "Every test in this record burned in orbit.";
  if (id === "earth") {
    if (!row) return "PSI holds one ground comparison, from SAFFIRE-II.";
    const word = (cell: string) => ({ full: "burned completely", none: "barely burned", partial: `burned ${cell}`, unknown: `burned ${cell}` })[burnExtent(cell)];
    return `One ground comparison is on record. SAFFIRE-II's ${row.thickness} ${row.material.toLowerCase()} ${word(row.oneGBurn)} at 1 g and ${word(row.microBurn)} in orbit.`;
  }
  return `No test at ${id === "moon" ? "Moon" : "Mars"} gravity is in PSI yet. NASA expects it from LUCI and FM2. Until then, orbit and Earth results bound the answer.`;
}

function pillarLines(reading: Reading, o2: number, noun: string, smoke: Props["smoke"]) {
  const { range } = reading;
  const prevent = !range
    ? `No ${noun} test with measured oxygen is in PSI.`
    : reading.beyond > 0
      ? `Nothing ${noun} has burned in orbit at this oxygen. The record stops at ${share(range[1])}, ${points(reading.beyond)} below this cabin.`
      : reading.below > 0
        ? `Leaner than any ${noun} test flown. The record starts at ${share(range[0])}.`
        : `Inside the oxygen range flown for ${noun} fuels, ${share(range[0])} to ${share(range[1])}.`;

  const nearSmoke = Math.abs(o2 - smoke.o2) <= TOLERANCE.o2 + 1e-9;
  const detect = nearSmoke
    ? `Smoke was measured near this oxygen: ${smoke.tests} tests in cabin air, assumed ${share(smoke.o2)}.`
    : `No smoke was measured at this oxygen. All ${smoke.tests} smoke tests ran in cabin air, assumed ${share(smoke.o2)}.`;

  const suppress =
    reading.richestOut === null
      ? `No ${noun} test with measured oxygen records how the flame ended.`
      : reading.outAtOrAbove > 0
        ? `${reading.outAtOrAbove} ${noun} ${plural(reading.outAtOrAbove, "flame", "flames")} went out on record at this oxygen or richer.`
        : `No ${noun} flame is on record going out at this oxygen. The richest that did ran at ${share(reading.richestOut)}.`;

  return { prevent, detect, suppress };
}

function Dial({ id, label, value, display, scale, onChange }: { id: string; label: string; value: number; display: string; scale: { min: number; max: number }; onChange: (value: number) => void }) {
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <span id={id} className="text-[13px] text-ink-2">
          {label}
        </span>
        <span className="mono text-[22px] font-medium leading-none">{display}</span>
      </div>
      <Slider.Root value={[value]} min={scale.min} max={scale.max} step={1} onValueChange={([next]) => onChange(next)} aria-labelledby={id} className="relative flex h-6 touch-none select-none items-center">
        <Slider.Track className="relative h-[3px] grow rounded-full bg-rule">
          <Slider.Range className="absolute h-full rounded-full bg-ink" />
        </Slider.Track>
        <Slider.Thumb className="block h-5 w-5 rounded-full border-2 border-ink bg-surface shadow transition-transform hover:scale-110 focus-visible:scale-110 active:scale-95" aria-label={label} />
      </Slider.Root>
    </div>
  );
}

function Flame({ g, label, verdict, pulse }: { g: number; label: string; verdict: Verdict; pulse: number }) {
  const stretch = Math.sqrt(g);
  const warm = Math.round(stretch * 100);
  const { fill, word } = VERDICT[verdict];
  const outer = `color-mix(in oklab, var(--s2) ${warm}%, var(--s1))`;
  const core = `color-mix(in oklab, var(--s4) ${warm}%, var(--surface))`;
  const spring = { type: "spring" as const, stiffness: 120, damping: 18 };
  const arrow = 64 * g;
  return (
    <svg viewBox="0 -24 200 264" role="img" aria-label={`Flame drawn for ${label} gravity. ${word}.`} className="mx-auto h-[250px] w-auto max-w-full">
      <motion.g initial={false} animate={{ y: 10 * stretch }} transition={spring}>
        <g className={pulse % 2 ? "flame-breathe-a" : "flame-breathe-b"}>
          <motion.path initial={false} animate={{ d: flamePath(g, 1.2) }} transition={spring} fill={outer} fillOpacity={0.06 + fill * 0.1} />
          <motion.path initial={false} animate={{ d: flamePath(g) }} transition={spring} fill={outer} fillOpacity={fill} stroke={outer} strokeWidth={1.5} strokeDasharray={verdict === "never" ? "4 5" : undefined} />
          <motion.path initial={false} animate={{ d: flamePath(g, 0.5) }} transition={spring} fill={core} fillOpacity={Math.min(1, fill + 0.08)} />
        </g>
      </motion.g>
      <path d="M62 210h76" stroke="var(--ink)" strokeWidth="3" strokeLinecap="round" />
      <path d="M100 210v18" stroke="var(--rule-strong)" strokeWidth="1.5" />
      <g stroke="var(--muted)" fill="none" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        {g === 0 ? <circle cx="178" cy="120" r="3.5" /> : <path d={`M178 100v${arrow.toFixed(1)}m-4.5 -6l4.5 6l4.5 -6`} />}
      </g>
      <text x="178" y="92" textAnchor="middle" className="mono" fontSize="10" fill="var(--muted)">
        {g} g
      </text>
    </svg>
  );
}

function Ruler({ range, o2, color }: { range: [number, number] | null; o2: number; color: string }) {
  const x = (fraction: number) => ((Math.min(1, Math.max(0.1, fraction)) * 100 - O2_SCALE.min) / (O2_SCALE.max - O2_SCALE.min)) * 300;
  return (
    <div aria-hidden="true">
      <svg viewBox="0 0 300 26" preserveAspectRatio="none" className="block h-[26px] w-full">
        <path d="M0 13h300" stroke="var(--rule-strong)" strokeWidth="1" />
        {range && <rect x={x(range[0])} y="9" width={Math.max(2, x(range[1]) - x(range[0]))} height="8" rx="2" fill={color} />}
        <path d={`M${x(0.21)} 5v16`} stroke="var(--muted)" strokeWidth="1" strokeDasharray="2 2" />
        <path d={`M${x(o2)} 1v24`} stroke="var(--accent)" strokeWidth="2.5" />
      </svg>
      <div className="mono mt-1 flex justify-between text-[10.5px] text-muted">
        <span>10% O2</span>
        <span>flown · cabin</span>
        <span>100%</span>
      </div>
    </div>
  );
}

export function CabinLab({ tests, smoke, scenarios, names, groundRow }: Props) {
  const first = scenarios.find((s) => s.id === "lunar_base") ?? scenarios[0];
  const start = first ? presetFor(first) : { o2: 0.3, kpa: 70 };
  const [o2Pct, setO2Pct] = useState(Math.round(start.o2 * 100));
  const [kpa, setKpa] = useState(start.kpa);
  const [phase, setPhase] = useState<Phase>("solid");
  const [gravity, setGravity] = useState<GravityId>(first ? (HABITAT_GRAVITY[first.id] ?? "orbit") : "orbit");
  const [habitat, setHabitat] = useState<string | null>(first?.id ?? null);
  const [pulse, setPulse] = useState(0);

  const o2 = o2Pct / 100;
  const reading = useMemo(() => readCabin(tests, { o2, kpa, phase }), [tests, o2, kpa, phase]);
  const noun = phase;
  const lines = pillarLines(reading, o2, noun, smoke);
  const verdict = VERDICT[reading.verdict];
  const field = GRAVITIES.find((item) => item.id === gravity) ?? GRAVITIES[0];
  const touch = () => setPulse((n) => n + 1);

  function chooseHabitat(id: string) {
    const scenario = scenarios.find((s) => s.id === id);
    if (!scenario) return;
    const preset = presetFor(scenario);
    setO2Pct(Math.round(preset.o2 * 100));
    setKpa(preset.kpa);
    setGravity(HABITAT_GRAVITY[id] ?? "orbit");
    setHabitat(id);
    touch();
  }

  const countLine =
    reading.close === 0
      ? `No ${noun} test flew within ${TOLERANCE.o2 * 100} oxygen points and ${TOLERANCE.kpa} kPa of this cabin.`
      : `${reading.close} ${noun} ${plural(reading.close, "test", "tests")} flew within ${TOLERANCE.o2 * 100} oxygen points and ${TOLERANCE.kpa} kPa of this cabin.`;
  const breath = Math.round(breathing({ o2, kpa }) * 100);
  const burn = Math.round(richer({ o2 }) * 100);

  return (
    <div>
      <header className="mb-8">
        <p className="eyebrow mb-3">Cabin lab</p>
        <h1 className="max-w-[18ch] text-[34px] font-semibold leading-[1.06] tracking-[-0.02em] sm:text-[48px]">Set a cabin. See what NASA burned there.</h1>
        <p className="mt-4 max-w-[52ch] text-[16px] leading-relaxed text-ink-2">
          Counted live from {tests.length} flight tests with measured oxygen. Nothing here is a prediction.
        </p>
      </header>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,4fr)_minmax(0,3fr)_minmax(0,5fr)]">
        <section aria-label="Cabin settings" className="panel flex flex-col gap-7 p-5">
          <div>
            <p className="eyebrow mb-3">Habitat</p>
            <ToggleGroup.Root type="single" value={habitat ?? ""} onValueChange={(value) => value && chooseHabitat(value)} aria-label="Habitat" className="grid grid-cols-3 gap-1.5">
              {scenarios.map((s) => (
                <ToggleGroup.Item key={s.id} value={s.id} className={CHIP}>
                  {HABITAT_SHORT_LABEL[s.id] ?? s.label}
                </ToggleGroup.Item>
              ))}
            </ToggleGroup.Root>
          </div>
          <Dial
            id="lab-o2"
            label="Oxygen in the air"
            value={o2Pct}
            display={`${o2Pct}%`}
            scale={O2_SCALE}
            onChange={(value) => {
              setO2Pct(value);
              setHabitat(null);
              touch();
            }}
          />
          <Dial
            id="lab-kpa"
            label="Cabin pressure"
            value={kpa}
            display={`${kpa} kPa`}
            scale={KPA_SCALE}
            onChange={(value) => {
              setKpa(value);
              setHabitat(null);
              touch();
            }}
          />
          <div>
            <p className="eyebrow mb-3">What is burning</p>
            <ToggleGroup.Root
              type="single"
              value={phase}
              onValueChange={(value) => {
                if (!value) return;
                setPhase(value as Phase);
                touch();
              }}
              aria-label="What is burning"
              className="grid grid-cols-3 gap-1.5"
            >
              {LAB_PHASES.map((p) => (
                <ToggleGroup.Item key={p} value={p} className={`${CHIP} text-left`}>
                  <span className="block font-medium">{PHASE_COPY[p].label}</span>
                  <span className="block pt-0.5 text-[11px] opacity-75">{PHASE_COPY[p].things}</span>
                </ToggleGroup.Item>
              ))}
            </ToggleGroup.Root>
          </div>
        </section>

        <section aria-label="Flame and gravity" className="panel flex flex-col p-5">
          <p className="eyebrow">Flame shape · illustration</p>
          <div className="flex flex-1 items-center py-2">
            <Flame g={field.g} label={field.label} verdict={reading.verdict} pulse={pulse} />
          </div>
          <ToggleGroup.Root
            type="single"
            value={gravity}
            onValueChange={(value) => {
              if (!value) return;
              setGravity(value as GravityId);
              touch();
            }}
            aria-label="Gravity"
            className="grid grid-cols-4 gap-1.5"
          >
            {GRAVITIES.map((item) => (
              <ToggleGroup.Item key={item.id} value={item.id} className={CHIP}>
                {item.label}
              </ToggleGroup.Item>
            ))}
          </ToggleGroup.Root>
          <p className="mt-3 min-h-[5.5em] text-[13px] leading-relaxed text-ink-2">{gravityLine(gravity, groundRow)}</p>
        </section>

        <section aria-label="Flight record for this cabin" aria-live="polite" className="panel flex flex-col p-5">
          <p className="eyebrow">NASA flight record</p>
          <p className="mt-3 text-[44px] font-semibold leading-none tracking-[-0.02em] sm:text-[52px]" style={{ color: verdict.color }}>
            {verdict.word}
          </p>
          <p className="mt-4 max-w-[40ch] text-[15px] leading-relaxed">{countLine}</p>
          {reading.recorded > 0 && (
            <p className="mt-1 max-w-[40ch] text-[15px] leading-relaxed text-ink-2">
              In {reading.wentOut} of the {reading.recorded} with a recorded ending, the flame went out.
            </p>
          )}
          <dl className="mt-6 grid grid-cols-2 gap-x-6 border-t border-rule pt-5">
            <div>
              <dt className="text-[12.5px] text-muted">To breathe</dt>
              <dd className="mono mt-1 text-[26px] font-medium leading-none">{breath}%</dd>
              <dd className="mt-1.5 text-[12.5px] text-ink-2">of sea-level oxygen pressure</dd>
            </div>
            <div>
              <dt className="text-[12.5px] text-muted">To burn</dt>
              <dd className="mono mt-1 text-[26px] font-medium leading-none">
                {burn > 0 ? "+" : ""}
                {burn}%
              </dd>
              <dd className="mt-1.5 text-[12.5px] text-ink-2">oxygen share against Earth air</dd>
            </div>
          </dl>
          <div className="mt-auto pt-6">
            <Ruler range={reading.range} o2={o2} color={PHASE_COLOR[phase]} />
          </div>
        </section>
      </div>

      <section className="mt-12">
        <h2 className="text-[24px] font-semibold leading-tight tracking-[-0.01em]">What the record says here</h2>
        <div className="mt-5 grid gap-x-10 gap-y-8 md:grid-cols-3">
          {(
            [
              ["Prevent", lines.prevent],
              ["Detect", lines.detect],
              ["Suppress", lines.suppress],
            ] as const
          ).map(([pillar, text]) => (
            <div key={pillar} className="border-t-2 border-ink pt-4">
              <h3 className="text-[13px] font-medium text-accent">{pillar}</h3>
              <p className="mt-2 max-w-[38ch] text-[15px] leading-relaxed">{text}</p>
              {pillar === "Detect" && (
                <p className="mt-3 flex flex-wrap gap-1">
                  {smoke.accessions.map((accession) => (
                    <Link key={accession} href={`/investigations/${accession}/`} className="mono rounded-[3px] border border-rule px-1.5 py-px text-[12px] text-ink-2 transition-colors hover:border-ink hover:text-ink">
                      {names[accession] ?? accession} · {accession}
                    </Link>
                  ))}
                </p>
              )}
            </div>
          ))}
        </div>
      </section>

      <section className="mt-12">
        <h2 className="text-[24px] font-semibold leading-tight tracking-[-0.01em]">Closest tests NASA flew</h2>
        <ol className="mt-5 divide-y divide-rule border-y border-rule">
          {reading.nearest.map((test) => (
            <li key={[test.a, test.o2, test.kpa, test.fuel, test.out].join("|")} className="grid grid-cols-2 items-baseline gap-x-4 gap-y-1 py-3 text-[14px] md:grid-cols-[minmax(0,3fr)_minmax(0,4fr)_minmax(0,3fr)_minmax(0,3fr)_3rem]">
              <Link href={`/investigations/${test.a}/`} className="link-underline justify-self-start font-medium">
                {names[test.a] ?? test.a}
              </Link>
              <span className="text-ink-2">{test.fuel || "fuel not recorded"}</span>
              <span className="mono text-[13px]">
                {share(test.o2)} O2 · {test.kpa === null ? "no pressure" : `${Math.round(test.kpa)} kPa`}
              </span>
              <span className="text-ink-2">{test.out || "ending not recorded"}</span>
              <span className="mono text-[13px] text-muted md:text-right">×{test.n}</span>
            </li>
          ))}
        </ol>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link href={habitat ? `/rank/?habitat=${habitat}` : "/rank/"} className="inline-flex h-11 items-center rounded-[4px] bg-ink px-5 text-[14px] font-medium text-paper transition-transform hover:-translate-y-px active:translate-y-px">
            Rank the experiments for this cabin
          </Link>
          <Link href="/ask/" className="inline-flex h-11 items-center rounded-[4px] border border-rule-strong px-5 text-[14px] font-medium transition-[transform,border-color] hover:-translate-y-px hover:border-ink active:translate-y-px">
            Ask the record a question
          </Link>
        </div>
      </section>
    </div>
  );
}
