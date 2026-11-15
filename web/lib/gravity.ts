import type { GravityNote, GravityRow } from "./types";

export type BurnExtent = "full" | "partial" | "none" | "unknown";

export const SAFFIRE2_SAMPLE_LENGTH_CM = 29;

export function burnExtent(text: string, sampleLengthCm = SAFFIRE2_SAMPLE_LENGTH_CM): BurnExtent {
  const cell = text.trim().toLowerCase();
  if (!cell) return "unknown";
  if (cell.includes("complete")) return "full";
  const match = cell.match(/^~?\s*(\d+(?:\.\d+)?)/);
  if (!match) return "unknown";
  const length = Number(match[1]);
  if (length === 0) return "none";
  return length >= sampleLengthCm ? "full" : "partial";
}

export function referencedNotes(rows: GravityRow[], notes: GravityNote[]): GravityNote[] {
  const cited = new Set<string>();
  for (const row of rows) {
    for (const cell of [row.microBurn, row.microSpread, row.oneGBurn, row.oneGSpread]) {
      for (const match of cell.matchAll(/note\s*(\d+)/gi)) cited.add(match[1]);
    }
  }
  return notes.filter((note) => cited.has(note.note));
}

export function thicknessLabel(thickness: string): string {
  return /^0\d/.test(thickness.trim()) ? `${thickness} (as written in NASA's table)` : thickness;
}
