"use client";

import { useEffect, useRef, useState } from "react";

// An original score, made in the browser from oscillators. No recording and no sample is loaded.
const CHORD_HZ = [73.42, 110, 146.83, 185, 220];
const LEVEL = 0.55;

interface Score {
  stop: () => void;
}

function startScore(): Score | null {
  const Context = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Context) return null;
  const audio = new Context();
  const master = audio.createGain();
  master.gain.value = 0;
  const filter = audio.createBiquadFilter();
  filter.type = "lowpass";
  filter.frequency.value = 700;
  const sweep = audio.createOscillator();
  const sweepDepth = audio.createGain();
  sweep.frequency.value = 0.04;
  sweepDepth.gain.value = 320;
  sweep.connect(sweepDepth).connect(filter.frequency);
  sweep.start();

  CHORD_HZ.forEach((hz, index) => {
    const level = 0.05 / (1 + index * 0.35);
    for (const detune of [-6, 6]) {
      const voice = audio.createOscillator();
      voice.type = index < 2 ? "sine" : "triangle";
      voice.frequency.value = hz;
      voice.detune.value = detune;
      const gain = audio.createGain();
      gain.gain.value = level;
      const swell = audio.createOscillator();
      const swellDepth = audio.createGain();
      swell.frequency.value = 0.03 + index * 0.011 + (detune > 0 ? 0.004 : 0);
      swellDepth.gain.value = level * 0.6;
      swell.connect(swellDepth).connect(gain.gain);
      swell.start();
      voice.connect(gain).connect(filter);
      voice.start();
    }
  });

  filter.connect(master).connect(audio.destination);
  master.gain.linearRampToValueAtTime(LEVEL, audio.currentTime + 3);

  return {
    stop: () => {
      master.gain.cancelScheduledValues(audio.currentTime);
      master.gain.setValueAtTime(master.gain.value, audio.currentTime);
      master.gain.linearRampToValueAtTime(0, audio.currentTime + 1);
      window.setTimeout(() => void audio.close().catch(() => undefined), 1100);
    },
  };
}

export function AmbientSound() {
  const score = useRef<Score | null>(null);
  const [on, setOn] = useState(false);

  useEffect(() => () => score.current?.stop(), []);

  function toggle() {
    if (score.current) {
      score.current.stop();
      score.current = null;
      setOn(false);
      return;
    }
    score.current = startScore();
    setOn(score.current !== null);
  }

  const label = on ? "Turn the ambient score off" : "Play the ambient score";
  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={on}
      aria-label={label}
      title={label}
      className={`inline-flex h-8 w-8 items-center justify-center rounded-[4px] border transition-[color,border-color,transform] hover:border-rule-strong hover:text-ink active:translate-y-px ${on ? "border-accent text-accent" : "border-rule text-ink-2"}`}
    >
      <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
        <path d="M3 6.5v3M6.3 4v8M9.7 5.5v5M13 7v2" />
        {!on && <path d="M2 14L14 2" strokeWidth="1.2" />}
      </svg>
    </button>
  );
}
