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
