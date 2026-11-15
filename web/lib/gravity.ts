export type BurnExtent = "full" | "partial" | "none" | "unknown";

// Every SAFFIRE-II sample was 29 cm long: the "Sample Length" column of NASA's table, and the PSI-99 record ("9 samples, each 5 cm x 29 cm").
export const SAFFIRE2_SAMPLE_LENGTH_CM = 29;

// Reads a burn-length cell of that table, for example "~ 0", "7.6 cm", "29 cm" or "Complete".
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
