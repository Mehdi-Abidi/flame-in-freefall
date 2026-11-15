"use client";

import { useState } from "react";
import * as ToggleGroup from "@radix-ui/react-toggle-group";
import { Flame } from "./Flame";

const PLACES = [
  { id: "orbit", label: "In orbit", g: 0 },
  { id: "earth", label: "On Earth", g: 1 },
];
const CHIP =
  "rounded-[4px] border border-rule px-4 py-2 text-[13px] text-ink-2 transition-[color,border-color,transform] hover:border-rule-strong hover:text-ink active:translate-y-px data-[state=on]:border-ink data-[state=on]:bg-ink data-[state=on]:text-paper";

/** The first thing a visitor can touch: the same flame with and without gravity. */
export function HeroFlame() {
  const [place, setPlace] = useState("orbit");
  const [pulse, setPulse] = useState(0);
  const current = PLACES.find((p) => p.id === place) ?? PLACES[0];
  return (
    <div className="flex flex-col items-center">
      <Flame g={current.g} label={current.label.toLowerCase()} fill={0.92} pulse={pulse} className="h-[320px] sm:h-[420px]" />
      <ToggleGroup.Root
        type="single"
        value={place}
        onValueChange={(value) => {
          if (!value) return;
          setPlace(value);
          setPulse((n) => n + 1);
        }}
        aria-label="Where the flame burns"
        className="mt-2 flex gap-1.5"
      >
        {PLACES.map((p) => (
          <ToggleGroup.Item key={p.id} value={p.id} className={CHIP}>
            {p.label}
          </ToggleGroup.Item>
        ))}
      </ToggleGroup.Root>
      <p className="eyebrow mt-4">Flame shape · illustration</p>
    </div>
  );
}
