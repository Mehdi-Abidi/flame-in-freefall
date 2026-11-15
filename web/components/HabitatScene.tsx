"use client";

import Image, { type StaticImageData } from "next/image";
import { AnimatePresence, motion } from "motion/react";
import earthrise from "@/assets/nasa/earthrise.jpg";
import earthset from "@/assets/nasa/earthset.jpg";
import mars from "@/assets/nasa/mars-murray-buttes.jpg";
import orbit from "@/assets/nasa/orbit-sunrise.jpg";

interface Scene {
  image: StaticImageData;
  alt: string;
  place: string;
  gravity: string;
  position: string;
}

/** Where each habitat is: a NASA photograph of the place, and the gravity there. */
const SCENES: Record<string, Scene> = {
  iss: { image: orbit, alt: "An orbital sunrise over Earth's horizon, photographed from the International Space Station", place: "Low Earth orbit", gravity: "Freefall · 0 g", position: "object-top" },
  lunar_base: { image: earthset, alt: "Earth setting behind the Moon's horizon, photographed from Orion on Artemis II", place: "The Moon", gravity: "Moon gravity · 0.165 g", position: "object-[50%_58%]" },
  pressurized_rover: { image: earthrise, alt: "Earth rising over the Moon's horizon, photographed from Apollo 8", place: "Driving on the Moon", gravity: "Moon gravity · 0.165 g", position: "object-[50%_78%]" },
  mars_habitat: { image: mars, alt: "The Murray Buttes on Mars, photographed by NASA's Curiosity rover", place: "Mars", gravity: "Mars gravity · 0.378 g", position: "object-center" },
  spacesuit: { image: orbit, alt: "Earth's horizon at night, photographed from the International Space Station", place: "Outside, on a spacewalk", gravity: "Freefall · 0 g", position: "object-[50%_35%]" },
};

interface Props {
  /** The habitat chosen, or null for a cabin the visitor set by hand. */
  id: string | null;
  label: string;
  air: string;
  /** Overrides the habitat's own gravity, for pages where gravity can be set separately. */
  gravity?: string;
  note?: string;
}

/** A banner that shows where the chosen habitat is. The photograph cross-fades when the habitat changes. */
export function HabitatScene({ id, label, air, gravity, note }: Props) {
  const scene = id ? SCENES[id] : undefined;
  return (
    <div data-wisp="This banner shows where the habitat you picked is: in orbit around Earth, on the Moon or on Mars. The photo is a real NASA picture of that place. The numbers are the air in that cabin and how strong gravity is there." className="hud-frame relative isolate mb-6 h-[190px] overflow-hidden sm:h-[230px]">
      <AnimatePresence initial={false}>
        {scene && (
          <motion.div key={id} initial={{ opacity: 0, scale: 1.06 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.8, ease: [0.2, 0.7, 0.2, 1] }} className="absolute inset-0 -z-20">
            <Image src={scene.image} alt={scene.alt} fill sizes="(min-width: 1240px) 1200px, 100vw" className={`object-cover ${scene.position}`} />
          </motion.div>
        )}
      </AnimatePresence>
      <div className="absolute inset-0 -z-10 bg-[linear-gradient(90deg,rgba(5,7,11,0.92)_0%,rgba(5,7,11,0.6)_45%,rgba(5,7,11,0.1)_100%)]" />
      <div className="flex h-full flex-col justify-end p-5 sm:p-6">
        <p className="eyebrow text-ice">
          {scene ? scene.place : "A cabin of your own"} · {gravity ?? scene?.gravity ?? "gravity as set below"}
        </p>
        <AnimatePresence mode="wait" initial={false}>
          <motion.p key={label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.25 }} className="display mt-2 text-[44px] sm:text-[64px]">
            {label}
          </motion.p>
        </AnimatePresence>
        <p className="mono mt-2 text-[13px] text-ink-2">
          {air}
          {note && <span className="text-accent"> · {note}</span>}
        </p>
      </div>
    </div>
  );
}
