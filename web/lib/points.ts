import { BASIS_LABEL } from "./format";
import type { Point } from "./types";

// What a dot on the gap map rests on: both values measured, only oxygen measured, or neither.
export type PointBasis = "measured" | "oxygen" | "assumed";

type Sources = Pick<Point, "o2Source" | "kpaSource">;

export function pointBasis(point: Sources): PointBasis {
  if (point.o2Source !== "measured") return "assumed";
  return point.kpaSource === "measured" ? "measured" : "oxygen";
}

export function oxygenMeasured(point: Sources): boolean {
  return pointBasis(point) !== "assumed";
}

// Tooltip text: says which of the two values was assumed or planned, and how.
export function basisLines(point: Sources): string[] {
  if (pointBasis(point) === "measured") return ["Oxygen and pressure measured"];
  return [`Oxygen: ${BASIS_LABEL[point.o2Source] ?? point.o2Source}`, `Pressure: ${BASIS_LABEL[point.kpaSource] ?? point.kpaSource}`];
}
