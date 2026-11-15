"use client";

import { motion } from "motion/react";
import { flamePath } from "@/lib/lab";

interface Props {
  g: number;
  label: string;
  /** How solid the flame is drawn: 1 where the record is rich, near 0 where nothing has flown. */
  fill: number;
  dashed?: boolean;
  /** Any change of this number makes the flame breathe twice. */
  pulse?: number;
  note?: string;
  className?: string;
}

/** A sphere with no gravity, a teardrop at 1 g. It shows what buoyancy does to the shape, nothing more. */
export function Flame({ g, label, fill, dashed = false, pulse = 0, note, className = "h-[250px]" }: Props) {
  const stretch = Math.sqrt(g);
  const warm = Math.round(stretch * 100);
  const outer = `color-mix(in oklab, var(--s2) ${warm}%, var(--s1))`;
  const core = `color-mix(in oklab, var(--s4) ${warm}%, color-mix(in oklab, var(--s1) 30%, white))`;
  const spring = { type: "spring" as const, stiffness: 120, damping: 18 };
  return (
    <svg viewBox="0 -24 200 264" role="img" aria-label={`Flame drawn for ${label} gravity.${note ? ` ${note}.` : ""}`} className={`mx-auto w-auto max-w-full ${className}`}>
      <motion.g initial={false} animate={{ y: 10 * stretch }} transition={spring}>
        <g className={pulse % 2 ? "flame-breathe-a" : "flame-breathe-b"}>
          <motion.path initial={false} animate={{ d: flamePath(g, 1.2) }} transition={spring} fill={outer} fillOpacity={0.06 + fill * 0.1} />
          <motion.path initial={false} animate={{ d: flamePath(g) }} transition={spring} fill={outer} fillOpacity={fill} stroke={outer} strokeWidth={1.5} strokeDasharray={dashed ? "4 5" : undefined} />
          <motion.path initial={false} animate={{ d: flamePath(g, 0.5) }} transition={spring} fill={core} fillOpacity={Math.min(1, fill + 0.08)} />
        </g>
      </motion.g>
      <path d="M62 210h76" stroke="var(--ink)" strokeWidth="3" strokeLinecap="round" />
      <path d="M100 210v18" stroke="var(--rule-strong)" strokeWidth="1.5" />
      <g stroke="var(--muted)" fill="none" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        {g === 0 ? <circle cx="178" cy="120" r="3.5" /> : <path d={`M178 100v${(64 * g).toFixed(1)}m-4.5 -6l4.5 6l4.5 -6`} />}
      </g>
      <text x="178" y="92" textAnchor="middle" className="mono" fontSize="10" fill="var(--muted)">
        {g} g
      </text>
    </svg>
  );
}
