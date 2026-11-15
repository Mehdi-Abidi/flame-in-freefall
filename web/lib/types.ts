export type Pillar = "prevention" | "detection" | "suppression";
export type Phase = "solid" | "liquid" | "gas" | "dust";
export type Range = [number, number];

export type Weights = Record<Pillar, number>;

export interface Scenario {
  id: string;
  label: string;
  o2: Range;
  kpa: Range;
  contextOnly: boolean;
  source: string;
  assumptions: string[];
}

export interface Components {
  condition_fit: number;
  material_relevance: number;
  pillar_match: number;
  data_richness: number;
}

export interface Evidence {
  n_considered: number;
  n_in_target: number;
  n_near: number;
  best: { o2_mole_fraction: number; pressure_kpa: number | null; closeness: number } | null;
}

export interface Rationale {
  text: string;
  source: "model" | "template";
  model: string;
}

export interface ScenarioScore {
  score: number;
  rank: number;
  components: Components;
  reasons: string[];
  evidence: Evidence;
  rationale: Rationale | null;
}

export interface Publication {
  title: string;
  authors: string;
}

export interface Investigation {
  accession: string;
  name: string;
  acronym: string | null;
  title: string;
  projectType: string | null;
  platform: string | null;
  hardware: string | null;
  pillars: Pillar[];
  pillarSource: string;
  phases: Phase[];
  o2Range: Range | null;
  o2Basis: string | null;
  kpaRange: Range | null;
  kpaBasis: string | null;
  nTests: number;
  nRecords: number;
  nFiles: number;
  publications: Publication[];
  psiUrl: string;
  summary: string | null;
  objective: string | null;
  fuels: string[];
  geometry: string[];
  sampleSize: string | null;
  varied: string[];
  fixed: string[];
  sensors: string[];
  measurements: string[];
  earthBenefits: string[];
  pillarReason: string | null;
  warnings: string[];
  scores: Record<string, ScenarioScore>;
}

export interface Point {
  a: string;
  ph: Phase;
  o2: number;
  kpa: number;
  o2Source: string;
  kpaSource: string;
  fuel: string;
  id: string;
}

export interface GravityRow {
  sample: string;
  material: string;
  thickness: string;
  flowDirection: string;
  microBurn: string;
  microSpread: string;
  oneGBurn: string;
  oneGSpread: string;
}

export interface PhaseOxygen {
  phase: Phase;
  min: number;
  max: number;
  count: number;
}

export interface Stats {
  investigations: number;
  records: number;
  rawFiles: number;
  rawTerabytes: number;
  solidTests: number;
  solidMaxO2: number;
  lunarTests: number;
  lunarPhases: Phase[];
  measuredRows: number;
  oxygenByPhase: PhaseOxygen[];
}

export interface BriefFinding {
  text: string;
  citations: string[];
}

export interface Brief {
  pillar: Pillar;
  title: string;
  findings: BriefFinding[];
  implication: string;
  gap: string;
  source: "model" | "template";
  model: string;
  review: string;
}

export interface Dataset {
  investigations: Investigation[];
  points: Point[];
  scenarios: Scenario[];
  componentWeights: Components;
  gravity: GravityRow[];
  briefs: Brief[];
  stats: Stats;
}
