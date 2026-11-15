"use client";

import { useEffect, useRef, useState } from "react";

// 'Signal to Noise' by Scott Buckley - released under CC-BY 4.0. www.scottbuckley.com.au
// The file in public/music is an excerpt of his recording, 1:00 to 2:46, made louder and faded at both ends so it loops.
const TRACK = `${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/music/signal-to-noise.mp3`;
const KEY = "flame-sound";
const LEVEL = 0.85;
const STEP = 0.05;
const MAX_STEPS = 40;

let player: HTMLAudioElement | null = null;
let fading: number | null = null;

/** Moves the volume to a target in small steps, then runs `done`. Some phones ignore volume changes, so it
 * also stops after a fixed number of steps. */
function fadeTo(target: number, done?: () => void) {
  const track = player;
  if (!track) return;
  if (fading !== null) window.clearInterval(fading);
  let steps = 0;
  fading = window.setInterval(() => {
    steps += 1;
    const gap = target - track.volume;
    if (Math.abs(gap) <= STEP || steps >= MAX_STEPS) {
      try {
        track.volume = target;
      } catch {}
      if (fading !== null) window.clearInterval(fading);
      fading = null;
      done?.();
      return;
    }
    track.volume = Math.min(1, Math.max(0, track.volume + Math.sign(gap) * STEP));
  }, 50);
}

/** Starts or resumes the track where it was paused. Resolves false when the browser refuses or the file is missing. */
function playTrack(): Promise<boolean> {
  if (!player) {
    player = new Audio(TRACK);
    player.loop = true;
    player.volume = 0;
  }
  return player
    .play()
    .then(() => {
      fadeTo(LEVEL);
      return true;
    })
    .catch(() => false);
}

function pauseTrack() {
  fadeTo(0, () => player?.pause());
}

function remember(state: "on" | "off") {
  try {
    sessionStorage.setItem(KEY, state);
  } catch {}
}

/** The music is on by default. Browsers allow no sound before a first click or key press, so it starts at that
 * moment, loops, pauses from the button and resumes from the same place. A pause lasts for that visit only, so
 * every new visit starts with music. */
export function AmbientSound() {
  const button = useRef<HTMLButtonElement>(null);
  const [on, setOn] = useState(false);

  useEffect(() => {
    let stored: string | null = null;
    try {
      stored = sessionStorage.getItem(KEY);
    } catch {}
    const forget = () => {
      window.removeEventListener("click", begin);
      window.removeEventListener("keydown", begin);
    };
    function begin(event: Event) {
      if (button.current?.contains(event.target as Node)) return;
      forget();
      void playTrack().then(setOn);
    }
    if (stored !== "off") {
      window.addEventListener("click", begin);
      window.addEventListener("keydown", begin);
    }
    return () => {
      forget();
      pauseTrack();
    };
  }, []);

  function toggle() {
    if (on) {
      pauseTrack();
      setOn(false);
      remember("off");
      return;
    }
    void playTrack().then(setOn);
    remember("on");
  }

  const label = on ? "Pause the music" : "Play the music";
  return (
    <button
      ref={button}
      type="button"
      onClick={toggle}
      aria-pressed={on}
      aria-label={label}
      title={label}
      className={`inline-flex h-8 w-8 items-center justify-center rounded-[2px] border transition-[color,border-color,transform] hover:border-rule-strong hover:text-ink active:translate-y-px ${on ? "border-accent text-accent" : "border-rule text-ink-2"}`}
    >
      <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
        <path d="M3 6.5v3M6.3 4v8M9.7 5.5v5M13 7v2" />
        {!on && <path d="M2 14L14 2" strokeWidth="1.2" />}
      </svg>
    </button>
  );
}
