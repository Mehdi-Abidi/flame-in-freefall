import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { parseCsv } from "./csv";
import type { Brief, Components, Dataset, GravityRow, Investigation, Phase, Pillar, Point, Range, Rationale, Scenario, ScenarioScore } from "./types";

const DATA_DIR = process.env.FLAME_DATA_DIR ?? path.join(process.cwd(), "..", "data");
const PHASES: Phase[] = ["solid", "liquid", "gas", "dust"];
const PILLARS: Pillar[] = ["prevention", "detection", "suppression"];
const POINT_RECORD_TYPES = new Set(["test", "condition_matrix", "test_day_condition"]);

function read(relative: string): string {
  const file = path.join(DATA_DIR, relative);
  try {
    return readFileSync(file, "utf-8");
  } catch (error) {
    throw new Error(`Dashboard data missing: ${file}. Run the pipeline in the repo root first. (${(error as Error).message})`);
  }
}

function readJson<T>(relative: string): T {
  try {
    return JSON.parse(read(relative)) as T;
  } catch (error) {
    if (error instanceof SyntaxError) throw new Error(`Dashboard data is not valid JSON: ${relative}. ${error.message}`);
    throw error;
  }
}

function num(value: string | undefined): number | null {
  if (value === undefined || value.trim() === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function range(value: unknown): Range | null {
  return Array.isArray(value) && value.length === 2 && value.every((v) => typeof v === "number") ? [value[0], value[1]] : null;
}

function list(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

interface RawInvestigation {
  accession: string;
  acronym: string | null;
  title: string;
  project_type: string | null;
  platform: string | null;
  hardware: string | null;
  fuel_phase: string[];
  o2_range: unknown;
  o2_basis: string | null;
  pressure_kpa_range: unknown;
  pressure_basis: string | null;
  n_tests: number;
  n_records: number;
  n_files: number | null;
  publications: { title: string; authors: string }[];
  psi_url: string;
}

interface RawExtracted {
  accession: string;
  summary: string | null;
  objective_short: string | null;
  fuels: string[];
  sample_geometry: string[];
  sample_size: string | null;
  variables_varied: string[];
  variables_fixed: string[];
  sensors: string[];
  measurements: string[];
  earth_benefits: string[];
  pillar_reason: string | null;
  warnings: string[];
}

interface RawRankingEntry {
  accession: string;
  score: number;
  rank: number;
  components: Components;
  pillars: string[];
  pillar_source: string;
  reasons: string[];
  evidence: ScenarioScore["evidence"];
}

interface RawRankings {
  component_weights: Components;
  scenarios: Record<string, {
    label: string;
    o2_mole_fraction: Range;
    pressure_kpa: Range;
    context_only: boolean;
    source: string;
    assumptions: string[];
    ranking: RawRankingEntry[];
  }>;
}

interface RawIndexEntry {
  accession: string;
  files: { file_count: number; total_bytes: number };
}

interface RawRationaleFile {
  rationales: Record<string, Record<string, { text: string; source: string; model: string; rank: number; score: number }>>;
}

function loadRationales(): RawRationaleFile["rationales"] {
  if (!existsSync(path.join(DATA_DIR, "processed/rationale.json"))) return {};
  const document = readJson<RawRationaleFile>("processed/rationale.json");
  return document && typeof document.rationales === "object" ? document.rationales : {};
}

function rationaleFor(raw: RawRationaleFile["rationales"], scenarioId: string, accession: string, rank: number): Rationale | null {
  const record = raw[scenarioId]?.[accession];
  if (!record || typeof record.text !== "string" || !record.text || record.rank !== rank) return null;
  return { text: record.text, source: record.source === "model" ? "model" : "template", model: record.model };
}

interface RawBriefFile {
  briefs: Record<string, Omit<Brief, "pillar">>;
}

function loadBriefs(knownAccessions: Set<string>): Brief[] {
  if (!existsSync(path.join(DATA_DIR, "processed/briefs.json"))) return [];
  const document = readJson<RawBriefFile>("processed/briefs.json");
  const order: Pillar[] = ["prevention", "detection", "suppression"];
  return order
    .filter((pillar) => document?.briefs?.[pillar])
    .map((pillar) => {
      const raw = document.briefs[pillar];
      return {
        pillar,
        title: raw.title,
        findings: (raw.findings ?? []).map((f) => ({ text: f.text, citations: (f.citations ?? []).filter((c) => knownAccessions.has(c)) })),
        implication: raw.implication,
        gap: raw.gap,
        source: raw.source === "model" ? "model" : "template",
        model: raw.model,
        review: raw.review,
      };
    });
}

function shortTitle(title: string): string {
  const cleaned = title.replace(/^Advanced Combustion via Microgravity Experiments\s*[-/]\s*/i, "ACME ").trim();
  return cleaned.length > 42 ? `${cleaned.slice(0, 40).trimEnd()}...` : cleaned;
}

function loadGravity(): GravityRow[] {
  return parseCsv(read("processed/saffire2_gravity.csv")).map((r) => ({
    sample: r.sample,
    material: r.material,
    thickness: r.thickness,
    flowDirection: r.flow_direction,
    microBurn: r.micro_g_burn_length,
    microSpread: r.micro_g_spread_length,
    oneGBurn: r.one_g_burn_length,
    oneGSpread: r.one_g_spread_rate,
  }));
}

let cache: Dataset | null = null;

export function loadDataset(): Dataset {
  if (cache) return cache;
  const investigations = readJson<RawInvestigation[]>("processed/investigations.json");
  const extracted = new Map(readJson<RawExtracted[]>("processed/extracted.json").map((r) => [r.accession, r]));
  const rankings = readJson<RawRankings>("processed/rankings.json");
  const index = readJson<RawIndexEntry[]>("raw/index.json");
  const rows = parseCsv(read("processed/tests.csv"));
  const rationales = loadRationales();

  const scenarios: Scenario[] = Object.entries(rankings.scenarios).map(([id, s]) => ({
    id,
    label: s.label,
    o2: s.o2_mole_fraction,
    kpa: s.pressure_kpa,
    contextOnly: s.context_only,
    source: s.source,
    assumptions: s.assumptions,
  }));

  const scoresByAccession = new Map<string, Record<string, ScenarioScore>>();
  const pillarsByAccession = new Map<string, { pillars: Pillar[]; source: string }>();
  for (const [id, scenario] of Object.entries(rankings.scenarios)) {
    for (const entry of scenario.ranking) {
      const scores = scoresByAccession.get(entry.accession) ?? {};
      scores[id] = {
        score: entry.score,
        rank: entry.rank,
        components: entry.components,
        reasons: entry.reasons,
        evidence: entry.evidence,
        rationale: rationaleFor(rationales, id, entry.accession, entry.rank),
      };
      scoresByAccession.set(entry.accession, scores);
      pillarsByAccession.set(entry.accession, {
        pillars: entry.pillars.filter((p): p is Pillar => (PILLARS as string[]).includes(p)),
        source: entry.pillar_source,
      });
    }
  }

  const merged: Investigation[] = investigations.map((inv) => {
    const ex = extracted.get(inv.accession);
    const pillars = pillarsByAccession.get(inv.accession) ?? { pillars: [], source: "none" };
    return {
      accession: inv.accession,
      name: inv.acronym || shortTitle(inv.title),
      acronym: inv.acronym,
      title: inv.title,
      projectType: inv.project_type,
      platform: inv.platform,
      hardware: inv.hardware,
      pillars: pillars.pillars,
      pillarSource: pillars.source,
      phases: (inv.fuel_phase ?? []).filter((p): p is Phase => (PHASES as string[]).includes(p)),
      o2Range: range(inv.o2_range),
      o2Basis: inv.o2_basis,
      kpaRange: range(inv.pressure_kpa_range),
      kpaBasis: inv.pressure_basis,
      nTests: inv.n_tests ?? 0,
      nRecords: inv.n_records ?? 0,
      nFiles: inv.n_files ?? 0,
      publications: inv.publications ?? [],
      psiUrl: inv.psi_url,
      summary: ex?.summary ?? null,
      objective: ex?.objective_short ?? null,
      fuels: list(ex?.fuels),
      geometry: list(ex?.sample_geometry),
      sampleSize: ex?.sample_size ?? null,
      varied: list(ex?.variables_varied),
      fixed: list(ex?.variables_fixed),
      sensors: list(ex?.sensors),
      measurements: list(ex?.measurements),
      earthBenefits: list(ex?.earth_benefits),
      pillarReason: ex?.pillar_reason ?? null,
      warnings: list(ex?.warnings),
      scores: scoresByAccession.get(inv.accession) ?? {},
    };
  });

  const points: Point[] = [];
  for (const r of rows) {
    if (!POINT_RECORD_TYPES.has(r.record_type)) continue;
    const o2 = num(r.o2_mole_fraction);
    const kpa = num(r.pressure_kpa);
    if (o2 === null || kpa === null || !(PHASES as string[]).includes(r.fuel_phase)) continue;
    points.push({
      a: r.accession,
      ph: r.fuel_phase as Phase,
      o2,
      kpa,
      measured: r.o2_source === "measured" && r.pressure_source === "measured",
      fuel: r.fuel,
      id: r.row_id,
    });
  }

  const solid = rows.filter((r) => r.fuel_phase === "solid" && r.o2_source === "measured").map((r) => num(r.o2_mole_fraction) ?? 0);
  const lunar = rows.filter((r) => {
    const o2 = num(r.o2_mole_fraction);
    const kpa = num(r.pressure_kpa);
    return r.record_type === "test" && r.o2_source === "measured" && o2 !== null && kpa !== null && o2 >= 0.3 && kpa <= 70.3;
  });

  cache = {
    investigations: merged,
    points,
    scenarios,
    componentWeights: rankings.component_weights,
    gravity: loadGravity(),
    briefs: loadBriefs(new Set(merged.map((i) => i.accession))),
    stats: {
      investigations: merged.length,
      records: rows.length,
      rawFiles: index.reduce((sum, e) => sum + (e.files?.file_count ?? 0), 0),
      rawTerabytes: index.reduce((sum, e) => sum + (e.files?.total_bytes ?? 0), 0) / 1e12,
      solidTests: solid.length,
      solidMaxO2: solid.length ? Math.max(...solid) : 0,
      lunarTests: lunar.length,
      lunarPhases: [...new Set(lunar.map((r) => r.fuel_phase as Phase))],
    },
  };
  return cache;
}
