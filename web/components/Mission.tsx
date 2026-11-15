"use client";

import Image from "next/image";
import Link from "next/link";
import { motion, useScroll, useTransform } from "motion/react";
import { useRef } from "react";
import earthrise from "@/assets/nasa/earthrise.jpg";
import earthset from "@/assets/nasa/earthset.jpg";
import flameEarth from "@/assets/nasa/flame-earth.jpg";
import flameOrbit from "@/assets/nasa/flame-orbit.jpg";
import saffireFabric from "@/assets/nasa/saffire-fabric.jpg";
import saffireBand from "@/assets/nasa/saffire-plexiglass.jpg";
import { Wisp } from "@/components/Guide";
import { Reveal } from "@/components/Reveal";
import { API_URL } from "@/lib/ask";
import type { HabitatReading } from "@/lib/guide";
import type { Verdict } from "@/lib/lab";

export interface MissionData {
  investigations: number;
  records: number;
  lunarTests: number;
  solid: { min: number; max: number; count: number };
  habitats: HabitatReading[];
  top: { accession: string; name: string; score: number }[];
  pipeline: { tables: number; rawTerabytes: number; summaries: number; habitats: number; scores: number; modelReasons: number };
}

const VERDICT: Record<Verdict, { word: string; color: string }> = {
  flown: { word: "Flown", color: "var(--good)" },
  thin: { word: "Barely flown", color: "var(--warn-ink)" },
  never: { word: "Never flown", color: "var(--signal)" },
};
const share = (fraction: number) => `${Number((fraction * 100).toFixed(1))}%`;

function Hero({ data }: { data: MissionData }) {
  const figures: [string, string][] = [
    [String(data.investigations), "investigations"],
    [data.records.toLocaleString("en-US"), "test records"],
    [String(data.lunarTests), "tests at lunar conditions"],
  ];
  return (
    <section className="relative isolate flex min-h-[calc(100svh-57px)] items-center overflow-hidden border-b border-rule">
      <div className="absolute inset-y-0 left-0 -z-20 w-[220%] lg:w-[135%]">
        <Image src={earthset} alt="Earth setting behind the Moon's horizon, photographed from Orion on Artemis II" fill priority sizes="135vw" className="object-cover object-bottom" />
      </div>
      <div className="absolute inset-0 -z-10 bg-[linear-gradient(90deg,rgba(5,7,11,0.96)_0%,rgba(5,7,11,0.74)_38%,rgba(5,7,11,0.12)_70%,rgba(5,7,11,0)_100%)]" />
      <div className="absolute inset-x-0 bottom-0 -z-10 h-40 bg-[linear-gradient(180deg,rgba(5,7,11,0),#05070b)]" />
      <div className="mx-auto w-full max-w-[1240px] px-4 py-16 sm:px-6">
        <p className="eyebrow hero-enter text-ice">SI-powered fire safety insights · NASA PSI combustion data</p>
        <h1 className="display hero-enter mt-5 max-w-[11ch] text-[64px] sm:text-[96px] lg:text-[124px]">
          A Moon base will breathe <span className="text-accent">30% oxygen</span>
        </h1>
        <p className="hero-enter-late mt-6 max-w-[44ch] text-[18px] leading-relaxed text-ink-2">
          NASA&apos;s fire tests on solid materials in orbit stopped at {share(data.solid.max)}. See what has burned in a cabin like yours, and what never has.
        </p>
        <div className="hero-enter-late mt-8 flex flex-wrap gap-3">
          <a href="#freefall" className="btn btn-primary">
            Begin the mission
          </a>
          <Link href="/lab/" className="btn btn-ghost">
            Open the cabin lab
          </Link>
        </div>
        <ul className="hero-enter-late mt-12 grid max-w-[640px] grid-cols-3 divide-x divide-rule-strong border border-rule-strong bg-paper/60 backdrop-blur-sm">
          {figures.map(([value, label]) => (
            <li key={label} className="px-4 py-3">
              <span className="display block text-[34px] sm:text-[46px]">{value}</span>
              <span className="eyebrow mt-1 block">{label}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="absolute bottom-5 left-1/2 hidden -translate-x-1/2 lg:block">
        <a href="#freefall" aria-label="Scroll to the first chapter" className="scroll-cue block text-[20px] text-ink-2">
          ↓
        </a>
      </div>
    </section>
  );
}

/** Scroll takes gravity away: NASA's candle on Earth fades into the same candle in freefall. */
function Freefall() {
  const scene = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: scene, offset: ["start start", "end end"] });
  const orbit = useTransform(scrollYProgress, [0.18, 0.72], [0, 1], { clamp: true });
  const earth = useTransform(orbit, (v) => 1 - v);
  const gravity = useTransform(orbit, (v) => (1 - v).toFixed(2));
  return (
    <section id="freefall" ref={scene} className="relative h-[230vh]">
      <div className="sticky top-0 flex h-[100svh] items-center overflow-hidden pt-14">
        <div className="mx-auto grid w-full max-w-[1240px] items-center gap-8 px-4 sm:px-6 lg:grid-cols-[minmax(0,6fr)_minmax(0,5fr)] lg:gap-16">
          <div>
            <p className="eyebrow text-accent">Chapter 1 · Freefall</p>
            <h2 className="display mt-3 text-[48px] sm:text-[84px]">Take gravity away</h2>
            <div className="mt-6 grid max-w-[40ch] text-[18px] leading-relaxed text-ink-2">
              <motion.p style={{ opacity: earth }} className="[grid-area:1/1]">
                On Earth, hot gas rises and pulls a flame into a teardrop. Keep scrolling.
              </motion.p>
              <motion.p style={{ opacity: orbit }} className="[grid-area:1/1]">
                In freefall nothing rises. The flame becomes a blue sphere that lives on diffusion, and fire spreads by different rules.
              </motion.p>
            </div>
            <div className="mt-10 max-w-[360px]">
              <div className="flex items-end justify-between">
                <span className="eyebrow">Gravity</span>
                <span className="display text-[56px] leading-none">
                  <motion.span>{gravity}</motion.span>
                  <span className="pl-2 text-[26px] text-ink-2">g</span>
                </span>
              </div>
              <div className="mt-2 h-1 bg-rule">
                <motion.div style={{ scaleX: earth }} className="h-full origin-left bg-accent" />
              </div>
              <div className="mono mt-2 flex justify-between text-[11px] text-muted">
                <span>Orbit</span>
                <span>Earth</span>
              </div>
            </div>
          </div>
          <div className="hud-frame relative mx-auto aspect-[5/8] max-h-[66svh] w-full max-w-[400px]">
            <motion.div style={{ opacity: earth }} className="absolute inset-0">
              <Image src={flameEarth} alt="A candle flame on Earth, tall and yellow, photographed by NASA" fill sizes="400px" className="object-cover" />
            </motion.div>
            <motion.div style={{ opacity: orbit }} className="absolute inset-0">
              <Image src={flameOrbit} alt="The same candle in microgravity: a small blue dome of flame, photographed by NASA" fill sizes="400px" className="object-cover" />
            </motion.div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Gap({ solid }: { solid: MissionData["solid"] }) {
  const x = (fraction: number) => `${((fraction - 0.1) / 0.3) * 100}%`;
  const span = (from: number, to: number) => `${((to - from) / 0.3) * 100}%`;
  return (
    <section className="mx-auto max-w-[1240px] px-4 py-24 sm:px-6">
      <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)]">
        <Reveal>
          <p className="eyebrow text-accent">Chapter 2 · The gap</p>
          <h2 className="display mt-3 text-[48px] sm:text-[84px]">Where the tests stop</h2>
          <div className="mt-8 flex flex-wrap items-end gap-x-12 gap-y-6">
            <div>
              <p className="display text-[84px] text-ice sm:text-[128px]">{share(solid.max)}</p>
              <p className="eyebrow mt-1">Richest solid test flown</p>
            </div>
            <div>
              <p className="display text-[84px] text-signal sm:text-[128px]">30%</p>
              <p className="eyebrow mt-1">Moon base cabin, or more</p>
            </div>
          </div>
          <div className="relative mt-10 h-12" aria-hidden="true">
            <div className="absolute inset-x-0 top-[9px] h-px bg-rule-strong" />
            <motion.div initial={{ scaleX: 0 }} whileInView={{ scaleX: 1 }} viewport={{ once: true }} transition={{ duration: 1, ease: [0.2, 0.7, 0.2, 1] }} className="absolute top-[4px] h-[11px] origin-left bg-ice" style={{ left: x(solid.min), width: span(solid.min, solid.max) }} />
            <div className="absolute top-[9px] border-t border-dashed border-signal" style={{ left: x(solid.max), width: span(solid.max, 0.3) }} />
            <div className="absolute top-0 h-[19px] border-x border-dashed border-signal bg-signal-wash" style={{ left: x(0.3), width: span(0.3, 0.4) }} />
            <div className="mono absolute inset-x-0 top-7 flex justify-between text-[11px] text-muted">
              <span>10% oxygen</span>
              <span>40%</span>
            </div>
          </div>
          <p className="mt-6 max-w-[44ch] text-[18px] leading-relaxed text-ink-2">
            {solid.count} solid-material tests with measured oxygen. None above {share(solid.max)}.
          </p>
          <Link href="/evidence/" className="btn btn-primary mt-8">
            See every test on the map
          </Link>
        </Reveal>
        <Reveal delay={0.1}>
          <div className="hud-frame relative aspect-[5/4] w-full">
            <Image src={saffireFabric} alt="A fabric sample burning inside NASA's Saffire-IV spacecraft fire experiment" fill sizes="(min-width: 1024px) 500px, 100vw" className="object-cover" />
          </div>
        </Reveal>
      </div>
    </section>
  );
}

function Cabin({ habitats }: { habitats: HabitatReading[] }) {
  return (
    <section className="relative isolate overflow-hidden border-y border-rule">
      <Image src={earthrise} alt="Earth rising over the Moon's horizon, photographed from Apollo 8" fill sizes="100vw" className="-z-20 object-cover object-[60%_70%]" />
      <div className="absolute inset-0 -z-10 bg-[linear-gradient(90deg,rgba(5,7,11,0.94)_0%,rgba(5,7,11,0.7)_55%,rgba(5,7,11,0.45)_100%)]" />
      <div className="mx-auto grid max-w-[1240px] items-center gap-12 px-4 py-24 sm:px-6 lg:grid-cols-2">
        <Reveal>
          <p className="eyebrow text-accent">Chapter 3 · Your cabin</p>
          <h2 className="display mt-3 text-[48px] sm:text-[84px]">What has burned in a cabin like yours</h2>
          <p className="mt-6 max-w-[42ch] text-[18px] leading-relaxed text-ink-2">Pick a habitat or set your own air. The lab counts the flight tests NASA ran near it.</p>
          <Link href="/lab/" className="btn btn-primary mt-8">
            Open the cabin lab
          </Link>
        </Reveal>
        <Reveal delay={0.1}>
          <ul className="panel divide-y divide-rule">
            {habitats.map((habitat) => {
              const solid = habitat.rows.find((row) => row.phase === "solid");
              if (!solid) return null;
              return (
                <li key={habitat.id}>
                  <Link href={`/lab/?habitat=${habitat.id}`} className="group flex items-center justify-between gap-4 px-5 py-5 transition-colors hover:bg-accent-wash">
                    <span>
                      <span className="display block text-[30px]">{habitat.label}</span>
                      <span className="mono mt-1 block text-[12px] text-muted">
                        {share(habitat.o2)} oxygen · {habitat.kpa} kPa · solid fuels{habitat.assumed ? " · assumed air" : ""}
                      </span>
                    </span>
                    <span className="text-right">
                      <span className="display block text-[30px]" style={{ color: VERDICT[solid.verdict].color }}>
                        {VERDICT[solid.verdict].word}
                      </span>
                      <span className="mono mt-1 block text-[12px] text-muted">
                        {solid.close} {solid.close === 1 ? "test" : "tests"} nearby
                      </span>
                    </span>
                  </Link>
                </li>
              );
            })}
          </ul>
        </Reveal>
      </div>
    </section>
  );
}

/** The data science in five steps, each with the number it produced. */
function Pipeline({ data }: { data: MissionData }) {
  const { pipeline } = data;
  const steps = [
    { name: "Ingest", figure: String(data.investigations), unit: "investigations", text: `${pipeline.tables} test tables and every record, pulled from NASA's PSI API. ${pipeline.rawTerabytes} TB of raw video stays at NASA, linked.` },
    { name: "Normalize", figure: data.records.toLocaleString("en-US"), unit: "test rows", text: "mmHg, atm and bar become kPa, in one table. Every value is tagged measured, planned or assumed." },
    { name: "Read", figure: String(pipeline.summaries), unit: "plain summaries", text: "An open model reads NASA's text. Facts the tables prove go in as ground truth, and anything it adds is flagged." },
    { name: "Rank", figure: String(pipeline.scores), unit: "scores", text: `A four-part formula with no model in it, for ${pipeline.habitats} habitats. Python and the browser agree on every score.` },
    { name: "Explain", figure: String(pipeline.modelReasons), unit: "checked reasons", text: "Model text is checked against the numbers before it is shown. Answers cite a NASA record or say the data does not cover it." },
  ];
  return (
    <section className="mx-auto max-w-[1240px] px-4 pt-24 sm:px-6">
      <Reveal>
        <p className="eyebrow text-accent">Chapter 4 · How it thinks</p>
        <h2 className="display mt-3 max-w-[14ch] text-[48px] sm:text-[84px]">From raw records to cited answers</h2>
      </Reveal>
      <ol className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {steps.map((step, index) => (
          <li key={step.name}>
            <Reveal delay={index * 0.06} className="h-full">
              <div className="panel flex h-full flex-col p-5">
                <span className="mono text-[12px] text-muted">0{index + 1}</span>
                <span className="display mt-1 text-[26px] text-accent">{step.name}</span>
                <span className="display mt-5 text-[56px] text-ice">{step.figure}</span>
                <span className="eyebrow mt-1">{step.unit}</span>
                <span className="mt-4 text-[14px] leading-relaxed text-ink-2">{step.text}</span>
              </div>
            </Reveal>
          </li>
        ))}
      </ol>
      <Reveal className="mt-8 flex flex-wrap gap-3">
        <Link href="/method/" className="btn btn-primary">
          Read the method
        </Link>
        <a href={`${API_URL}/export`} className="btn btn-ghost">
          Download the test table
        </a>
      </Reveal>
    </section>
  );
}

function Tools({ data }: { data: MissionData }) {
  return (
    <section className="mx-auto max-w-[1240px] px-4 py-24 sm:px-6">
      <Reveal>
        <p className="eyebrow text-accent">Chapter 5 · Mission tools</p>
        <h2 className="display mt-3 text-[48px] sm:text-[84px]">Go deeper</h2>
      </Reveal>
      <div className="mt-10 grid gap-4 md:grid-cols-6">
        <Reveal className="md:col-span-4">
          <Link href="/rank/?habitat=lunar_base" className="panel bento p-6">
            <span className="eyebrow">Rank · Moon base</span>
            <span className="display mt-2 text-[40px]">Which experiments matter most</span>
            <ol className="mt-6 space-y-3">
              {data.top.map((item, index) => (
                <li key={item.accession} className="grid grid-cols-[28px_minmax(0,1fr)_44px] items-center gap-3">
                  <span className="mono text-[13px] text-muted">0{index + 1}</span>
                  <span>
                    <span className="block text-[15px] font-medium">{item.name}</span>
                    <span className="mt-1.5 block h-1 bg-rule">
                      <span className="block h-full bg-accent" style={{ width: `${item.score}%` }} />
                    </span>
                  </span>
                  <span className="display text-right text-[26px]">{item.score}</span>
                </li>
              ))}
            </ol>
            <span className="mt-auto flex items-center gap-2 pt-6 text-[14px] text-ink-2">
              Re-rank all {data.investigations} for any habitat
              <span className="arrow text-accent" aria-hidden="true">
                →
              </span>
            </span>
          </Link>
        </Reveal>
        <Reveal className="md:col-span-2" delay={0.05}>
          <Link href="/ask/" className="panel bento items-start p-6">
            <Wisp size={84} />
            <span className="display mt-4 text-[40px]">Ask Wisp</span>
            <span className="mt-2 text-[15px] leading-relaxed text-ink-2">Your guide on every page. Type or speak, and answers from the record cite it.</span>
            <span className="arrow mt-auto pt-6 text-accent" aria-hidden="true">
              →
            </span>
          </Link>
        </Reveal>
        <Reveal className="md:col-span-2">
          <Link href="/investigations/" className="panel bento p-6">
            <span className="display text-[96px] text-ice">{data.investigations}</span>
            <span className="display text-[30px]">Investigations</span>
            <span className="mt-2 text-[15px] leading-relaxed text-ink-2">Each one in plain words, with its tests and papers.</span>
            <span className="arrow mt-auto pt-6 text-accent" aria-hidden="true">
              →
            </span>
          </Link>
        </Reveal>
        <Reveal className="md:col-span-2" delay={0.05}>
          <Link href="/compare/" className="panel bento p-6">
            <span className="flex gap-1.5" aria-hidden="true">
              {[64, 96, 44, 80].map((height, index) => (
                <span key={index} className={`w-7 self-end ${index === 1 ? "bg-accent" : "bg-rule-strong"}`} style={{ height }} />
              ))}
            </span>
            <span className="display mt-4 text-[30px]">Compare</span>
            <span className="mt-2 text-[15px] leading-relaxed text-ink-2">Up to four side by side, differences marked.</span>
            <span className="arrow mt-auto pt-6 text-accent" aria-hidden="true">
              →
            </span>
          </Link>
        </Reveal>
        <Reveal className="md:col-span-2" delay={0.1}>
          <Link href="/method/" className="panel bento p-6">
            <span className="mono text-[13px] leading-relaxed text-ink-2">
              fit 0.35
              <br />
              pillar 0.25
              <br />
              material 0.20
              <br />
              data 0.20
            </span>
            <span className="display mt-4 text-[30px]">Method</span>
            <span className="mt-2 text-[15px] leading-relaxed text-ink-2">How every score and sentence is made and checked.</span>
            <span className="arrow mt-auto pt-6 text-accent" aria-hidden="true">
              →
            </span>
          </Link>
        </Reveal>
        <Reveal className="md:col-span-6">
          <Link href="/earth/" className="panel bento relative isolate min-h-[220px] justify-end p-6">
            <Image src={saffireBand} alt="A line of small flames along burning plexiglass in NASA's Saffire-IV experiment" fill sizes="(min-width: 1240px) 1200px, 100vw" className="-z-20 object-cover opacity-80" />
            <span className="absolute inset-0 -z-10 bg-[linear-gradient(90deg,rgba(5,7,11,0.92)_0%,rgba(5,7,11,0.5)_60%,rgba(5,7,11,0.2)_100%)]" />
            <span className="eyebrow">Back on Earth</span>
            <span className="display mt-2 flex items-center gap-3 text-[40px]">
              Where this research lands at home
              <span className="arrow text-accent" aria-hidden="true">
                →
              </span>
            </span>
          </Link>
        </Reveal>
      </div>
    </section>
  );
}

function Close() {
  return (
    <section className="border-t border-rule">
      <Reveal className="mx-auto max-w-[1240px] px-4 py-24 text-center sm:px-6">
        <p className="eyebrow text-accent">Next flights</p>
        <h2 className="display mx-auto mt-3 max-w-[16ch] text-[48px] sm:text-[84px]">Four experiments would close the gap</h2>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link href="/evidence/#next" className="btn btn-primary">
            See the four experiments
          </Link>
          <Link href="/lab/" className="btn btn-ghost">
            Open the cabin lab
          </Link>
        </div>
      </Reveal>
    </section>
  );
}

export function Mission({ data }: { data: MissionData }) {
  return (
    <>
      <Hero data={data} />
      <Freefall />
      <Gap solid={data.solid} />
      <Cabin habitats={data.habitats} />
      <Pipeline data={data} />
      <Tools data={data} />
      <Close />
    </>
  );
}
