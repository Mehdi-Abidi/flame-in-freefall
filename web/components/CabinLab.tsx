"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import * as Slider from "@radix-ui/react-slider";
import * as ToggleGroup from "@radix-ui/react-toggle-group";
import { HABITAT_SHORT_LABEL, PHASE_COLOR } from "@/lib/format";
import { Flame } from "@/components/Flame";
import { HabitatScene } from "@/components/HabitatScene";
import { burnExtent } from "@/lib/gravity";
import { GRAVITIES, LAB_PHASES, TOLERANCE, breathing, isAssumed, isClose, presetFor, readCabin, richer, type Cabin, type GravityId, type LabTest, type Reading, type Verdict } from "@/lib/lab";
import { screen } from "@/lib/screen";
import type { GravityRow, Phase, Scenario } from "@/lib/types";

interface Props {
  tests: LabTest[];
  smoke: { tests: number; o2: number; accessions: string[] };
  scenarios: Scenario[];
  names: Record<string, string>;
  groundRow: GravityRow | null;
  startHabitat?: string;
}

const PHASE_COPY: Record<string, { label: string; things: string }> = {
  solid: { label: "Solid", things: "Fabrics, plastics" },
  liquid: { label: "Liquid", things: "Fuel droplets" },
  gas: { label: "Gas", things: "Gas flames" },
};

const VERDICT: Record<Verdict, { word: string; color: string; fill: number }> = {
  flown: { word: "Flown", color: "var(--good)", fill: 0.92 },
  thin: { word: "Barely flown", color: "var(--warn-ink)", fill: 0.5 },
  never: { word: "Never flown", color: "var(--signal)", fill: 0.1 },
};

const HABITAT_GRAVITY: Record<string, GravityId> = { lunar_base: "moon", pressurized_rover: "moon", mars_habitat: "mars" };
// Named in NASA's BRE record (PSI-20): "14.7 psia, 21 % oxygen: 10.2 psia, 26.5 %; and 8.2 psia, 34 % oxygen."
const CANDIDATES = [
  { label: "10.2 psi · 26.5% O2", o2: 26.5, kpa: 70 },
  { label: "8.2 psi · 34% O2", o2: 34, kpa: 57 },
];
const O2_SCALE = { min: 10, max: 100 };
const KPA_SCALE = { min: 20, max: 105 };
const CHIP =
  "rounded-[4px] border border-rule px-2 py-2 text-[12.5px] text-ink-2 transition-[color,border-color,transform] hover:border-rule-strong hover:text-ink active:translate-y-px data-[state=on]:border-accent data-[state=on]:bg-accent data-[state=on]:text-accent-ink";

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

function Dial({ id, label, value, display, scale, step = 1, onChange }: { id: string; label: string; value: number; display: string; scale: { min: number; max: number }; step?: number; onChange: (value: number) => void }) {
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <span id={id} className="text-[13px] text-ink-2">
          {label}
        </span>
        <span className="mono text-[22px] font-medium leading-none">{display}</span>
      </div>
      <Slider.Root value={[value]} min={scale.min} max={scale.max} step={step} onValueChange={([next]) => onChange(next)} aria-labelledby={id} className="relative flex h-6 touch-none select-none items-center">
        <Slider.Track className="relative h-[3px] grow rounded-full bg-rule">
          <Slider.Range className="absolute h-full rounded-full bg-ink" />
        </Slider.Track>
        <Slider.Thumb className="block h-5 w-5 rounded-full border-2 border-ink bg-surface shadow transition-transform hover:scale-110 focus-visible:scale-110 active:scale-95" aria-label={label} />
      </Slider.Root>
    </div>
  );
}

const MAP = { o2: [0.1, 0.45], kpa: [20, 125], w: 320, h: 190, left: 30, right: 8, top: 8, bottom: 22 };

/** Every NASA test as a dot by oxygen and pressure, with a box around the cabin. Dots inside the box are the tests
 * the big word counts. */
function CabinMap({ tests, cabin }: { tests: LabTest[]; cabin: Cabin }) {
  const dots = useMemo(() => {
    const seen = new Map<string, LabTest>();
    for (const test of tests) {
      if (test.kpa === null || test.kpa > MAP.kpa[1] || test.o2 > MAP.o2[1]) continue;
      const key = `${test.ph}|${Math.round(test.o2 * 200)}|${Math.round(test.kpa / 2)}`;
      if (!seen.has(key)) seen.set(key, test);
    }
    return [...seen.values()];
  }, [tests]);
  const clamp = (value: number, [low, high]: number[]) => Math.min(high, Math.max(low, value));
  const x = (o2: number) => MAP.left + ((clamp(o2, MAP.o2) - MAP.o2[0]) / (MAP.o2[1] - MAP.o2[0])) * (MAP.w - MAP.left - MAP.right);
  const y = (kpa: number) => MAP.h - MAP.bottom - ((clamp(kpa, MAP.kpa) - MAP.kpa[0]) / (MAP.kpa[1] - MAP.kpa[0])) * (MAP.h - MAP.top - MAP.bottom);
  const offChart = cabin.o2 > MAP.o2[1];
  const box = { x: x(cabin.o2 - TOLERANCE.o2), y: y(cabin.kpa + TOLERANCE.kpa), w: x(cabin.o2 + TOLERANCE.o2) - x(cabin.o2 - TOLERANCE.o2), h: y(cabin.kpa - TOLERANCE.kpa) - y(cabin.kpa + TOLERANCE.kpa) };
  return (
    <figure className="m-0">
      <svg viewBox={`0 0 ${MAP.w} ${MAP.h}`} role="img" aria-label="NASA's tests by oxygen and pressure, with a box around this cabin" className="block w-full">
        {[0.1, 0.2, 0.3, 0.4].map((o2) => (
          <g key={o2}>
            <path d={`M${x(o2)} ${MAP.top}V${MAP.h - MAP.bottom}`} stroke="var(--rule)" strokeWidth="1" />
            <text x={x(o2)} y={MAP.h - 8} textAnchor="middle" className="mono" fontSize="8.5" fill="var(--muted)">
              {o2 * 100}%
            </text>
          </g>
        ))}
        {[30, 50, 70, 101].map((kpa) => (
          <g key={kpa}>
            <path d={`M${MAP.left} ${y(kpa)}H${MAP.w - MAP.right}`} stroke="var(--rule)" strokeWidth="1" />
            <text x={MAP.left - 5} y={y(kpa) + 3} textAnchor="end" className="mono" fontSize="8.5" fill="var(--muted)">
              {kpa}
            </text>
          </g>
        ))}
        {dots
          .filter((dot) => dot.ph !== cabin.phase)
          .map((dot, index) => (
            <circle key={`o${index}`} cx={x(dot.o2)} cy={y(dot.kpa ?? 0)} r="1.5" fill="var(--rule-strong)" />
          ))}
        {!offChart && <rect x={box.x} y={box.y} width={box.w} height={box.h} fill="var(--accent-wash)" stroke="var(--accent)" strokeWidth="1.5" />}
        {dots
          .filter((dot) => dot.ph === cabin.phase)
          .map((dot, index) => {
            const inside = isClose(dot, cabin);
            return <circle key={`s${index}`} cx={x(dot.o2)} cy={y(dot.kpa ?? 0)} r={inside ? 3.2 : 2.2} fill={PHASE_COLOR[cabin.phase]} stroke={inside ? "var(--ink)" : "none"} strokeWidth="1" />;
          })}
        {offChart ? (
          <text x={MAP.w - MAP.right - 4} y={MAP.top + 12} textAnchor="end" className="mono" fontSize="9" fill="var(--signal)">
            your cabin is past this chart →
          </text>
        ) : (
          <path d={`M${x(cabin.o2) - 5} ${y(cabin.kpa)}h10M${x(cabin.o2)} ${y(cabin.kpa) - 5}v10`} stroke="var(--accent)" strokeWidth="1.5" />
        )}
      </svg>
      <figcaption className="mono mt-1 text-[10.5px] leading-relaxed text-muted">Oxygen across, pressure in kPa up. Each dot is a NASA test, coloured when it burned your fuel type. The box is near your cabin.</figcaption>
    </figure>
  );
}

/** Opens on the habitat named in the address, for example /lab/?habitat=mars_habitat. */
export function CabinLabFromUrl(props: Props) {
  const requested = useSearchParams().get("habitat");
  const known = props.scenarios.some((s) => s.id === requested) ? (requested as string) : undefined;
  return <CabinLab key={known ?? "default"} {...props} startHabitat={known} />;
}

export function CabinLab({ tests, smoke, scenarios, names, groundRow, startHabitat }: Props) {
  const first = scenarios.find((s) => s.id === (startHabitat ?? "lunar_base")) ?? scenarios[0];
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

  // Tell the guide what this screen shows, so "why does it say that?" can be answered about these exact settings.
  useEffect(() => {
    screen.set(`The cabin lab is set to ${o2Pct}% oxygen at ${kpa} kPa, ${phase} fuels, ${field.label} gravity. It reads ${verdict.word}: ${reading.close} ${phase} ${plural(reading.close, "test", "tests")} near this cabin.`);
    return () => screen.set("");
  }, [o2Pct, kpa, phase, field.label, verdict.word, reading.close]);

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
      <header className="hero-enter mb-8">
        <p className="eyebrow mb-3 text-accent">Stage 2 of 9 · Cabin lab</p>
        <h1 className="display max-w-[14ch] text-[52px] sm:text-[80px]">What NASA has burned in a cabin like yours</h1>
        <p className="mt-4 max-w-[52ch] text-[16px] leading-relaxed text-ink-2">
          Counted live from {tests.length} flight tests with measured oxygen. Nothing here is a prediction.
        </p>
      </header>

      <HabitatScene
        id={habitat}
        label={habitat ? (HABITAT_SHORT_LABEL[habitat] ?? habitat) : "Your own cabin"}
        air={`${o2Pct}% oxygen · ${kpa} kPa`}
        gravity={field.g === 0 ? "Freefall · 0 g" : `${field.label} gravity · ${field.g} g`}
        note={scenarios.some((s) => s.id === habitat && isAssumed(s)) ? "assumed air" : undefined}
      />

      <ol className="mb-4 grid gap-4 md:grid-cols-3">
        {[
          ["1 · Set the air", "Pick a habitat or drag oxygen and pressure."],
          ["2 · Watch the box", "It moves across NASA's tests. Dots inside it are tests near your cabin."],
          ["3 · Read the word", "Flown is 10 or more tests inside. Barely flown is 1 to 9. Never flown is none, so nobody knows."],
        ].map(([step, line]) => (
          <li key={step} className="border-l-2 border-accent pl-3">
            <span className="display block text-[20px]">{step}</span>
            <span className="mt-1 block text-[13.5px] leading-relaxed text-ink-2">{line}</span>
          </li>
        ))}
      </ol>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,4fr)_minmax(0,3fr)_minmax(0,5fr)]">
        <section aria-label="Cabin settings" data-wisp="This is where you describe a cabin: how much oxygen is in the air, how strong the air pressure is, and what kind of thing is burning. Pick a ready-made habitat, or drag the sliders to make your own." className="panel flex flex-col gap-7 p-5">
          <div>
            <p className="eyebrow mb-3">Habitat</p>
            <ToggleGroup.Root type="single" value={habitat ?? ""} onValueChange={(value) => value && chooseHabitat(value)} aria-label="Habitat" className="grid grid-cols-3 gap-1.5">
              {scenarios.map((s) => (
                <ToggleGroup.Item key={s.id} value={s.id} className={CHIP}>
                  {HABITAT_SHORT_LABEL[s.id] ?? s.label}
                </ToggleGroup.Item>
              ))}
            </ToggleGroup.Root>
            <p className="eyebrow mb-2 mt-5">NASA&apos;s candidate cabins</p>
            <div className="grid grid-cols-2 gap-1.5">
              {CANDIDATES.map((candidate) => {
                const on = habitat === null && o2Pct === candidate.o2 && kpa === candidate.kpa;
                return (
                  <button
                    key={candidate.label}
                    type="button"
                    aria-pressed={on}
                    onClick={() => {
                      setO2Pct(candidate.o2);
                      setKpa(candidate.kpa);
                      setHabitat(null);
                      touch();
                    }}
                    className={`mono rounded-[4px] border px-2 py-2 text-[11.5px] transition-[color,border-color,transform] active:translate-y-px ${on ? "border-accent bg-accent text-accent-ink" : "border-rule text-ink-2 hover:border-rule-strong hover:text-ink"}`}
                  >
                    {candidate.label}
                  </button>
                );
              })}
            </div>
            <p className="mt-2 text-[12px] leading-relaxed text-muted">
              Named for human missions in NASA&apos;s{" "}
              <Link href="/investigations/PSI-20/" className="link-underline text-ink-2">
                BRE record
              </Link>
              .
            </p>
            {scenarios.some((s) => s.id === habitat && isAssumed(s)) && (
              <p className="mt-2 text-[12px] leading-relaxed text-muted">Assumed. The challenge gives no atmosphere for this habitat, so it uses the lunar base&apos;s.</p>
            )}
          </div>
          <Dial
            id="lab-o2"
            label="Oxygen in the air"
            value={o2Pct}
            display={`${o2Pct}%`}
            scale={O2_SCALE}
            step={0.5}
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

        <section aria-label="Flame and gravity" data-wisp="This drawing shows how gravity changes the shape of a flame: pointed on Earth, round in space. It is only a drawing, not a result. The words under it tell you what real evidence NASA has for the gravity you picked." className="panel flex flex-col p-5">
          <p className="eyebrow">Flame shape · illustration</p>
          <div className="flex flex-1 items-center py-2">
            <Flame g={field.g} label={field.label} fill={verdict.fill} dashed={reading.verdict === "never"} note={verdict.word} pulse={pulse} />
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

        <section aria-label="Flight record for this cabin" aria-live="polite" data-wisp="This is the answer for your cabin. The big word says whether NASA has ever run fire tests in air like yours. On the map, every dot is a real NASA test, and the orange box means close to your cabin. Dots inside the box are the tests that count. No dots inside means nobody has tested it." className="panel flex flex-col p-5">
          <p className="eyebrow">NASA flight record</p>
          <p className="display mt-3 text-[64px] sm:text-[88px]" style={{ color: verdict.color }}>
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
            <CabinMap tests={tests} cabin={{ o2, kpa, phase }} />
          </div>
        </section>
      </div>

      <section className="mt-12" data-wisp="These are three plain facts about your cabin, one for each part of fire safety: stopping a fire from starting, noticing it early, and putting it out.">
        <h2 className="display text-[36px] sm:text-[46px]">What the record says here</h2>
        <div className="mt-5 grid gap-4 md:grid-cols-3">
          {(
            [
              ["Prevent", lines.prevent],
              ["Detect", lines.detect],
              ["Suppress", lines.suppress],
            ] as const
          ).map(([pillar, text]) => (
            <div key={pillar} className="panel p-5">
              <h3 className="display text-[26px] text-accent">{pillar}</h3>
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

      <section className="mt-12" data-wisp="These are the real NASA tests whose air was most like your cabin's. Each row says which experiment it was, what burned, how much oxygen and pressure it had, and how it ended.">
        <h2 className="display text-[36px] sm:text-[46px]">Closest tests NASA flew</h2>
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
          <Link href={habitat ? `/rank/?habitat=${habitat}` : "/rank/"} className="btn btn-primary">
            Rank the experiments for this cabin
          </Link>
          <Link href="/ask/" className="btn btn-ghost">
            Ask the record a question
          </Link>
        </div>
      </section>
    </div>
  );
}
