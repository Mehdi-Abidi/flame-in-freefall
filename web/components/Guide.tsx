"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState, useSyncExternalStore, type FormEvent } from "react";
import { ask, splitCitations, type AskAnswer } from "@/lib/ask";
import { PHASE_LABEL } from "@/lib/format";
import { localReply, suggestionsFor, type GuideData, type GuideLink, type HabitatReading } from "@/lib/guide";
import type { Verdict } from "@/lib/lab";

type Message =
  | { id: number; from: "you"; text: string }
  | { id: number; from: "orb"; text?: string; habitat?: HabitatReading; link?: GuideLink; answer?: AskAnswer; error?: string };

interface Recognizer {
  lang: string;
  interimResults: boolean;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
  start: () => void;
  stop: () => void;
}

const VERDICT: Record<Verdict, { word: string; color: string }> = {
  flown: { word: "Flown", color: "var(--good)" },
  thin: { word: "Barely flown", color: "var(--warn-ink)" },
  never: { word: "Never flown", color: "var(--signal)" },
};
const HELLO = "I am Orb, your guide. Ask me about NASA's fire tests, or name a habitat and I will check its cabin.";
const ICON = "inline-flex h-8 w-8 items-center justify-center rounded-[4px] border border-rule text-ink-2 transition-[color,border-color,transform] hover:border-rule-strong hover:text-ink active:translate-y-px";
const noSubscription = () => () => {};

function newRecognizer(): Recognizer | null {
  const scope = window as unknown as Record<string, (new () => Recognizer) | undefined>;
  const Speech = scope.SpeechRecognition ?? scope.webkitSpeechRecognition;
  return Speech ? new Speech() : null;
}

/** Orb: a flame in freefall with a face. A blue sphere, an orbit ring and one small ember. */
export function Orb({ size = 44, busy = false }: { size?: number; busy?: boolean }) {
  return (
    <svg viewBox="0 0 64 64" width={size} height={size} aria-hidden="true" className="shrink-0">
      <ellipse cx="32" cy="34" rx="29" ry="9" fill="none" stroke="var(--rule-strong)" strokeWidth="1.5" transform="rotate(-18 32 34)" />
      <circle cx="32" cy="32" r="19" fill="var(--s1)" />
      <circle cx="32" cy="34" r="12.5" fill="color-mix(in oklab, var(--s1) 32%, white)" />
      <g className={busy ? "orb-blink" : undefined}>
        <ellipse cx="25.5" cy="31" rx="2.6" ry="3.6" fill="#0b1020" />
        <ellipse cx="38.5" cy="31" rx="2.6" ry="3.6" fill="#0b1020" />
        <circle cx="26.4" cy="29.6" r="0.9" fill="#ffffff" />
        <circle cx="39.4" cy="29.6" r="0.9" fill="#ffffff" />
      </g>
      <path d="M28.5 38.5q3.5 2.6 7 0" fill="none" stroke="#0b1020" strokeWidth="1.5" strokeLinecap="round" />
      <circle cx="59.4" cy="25.2" r="2.4" fill="var(--signal)" />
    </svg>
  );
}

function HabitatCard({ habitat }: { habitat: HabitatReading }) {
  return (
    <dl className="mt-3 divide-y divide-rule rounded-[4px] border border-rule bg-paper">
      {habitat.rows.map((row) => (
        <div key={row.phase} className="flex items-baseline justify-between gap-3 px-3 py-2">
          <dt className="text-[13px] text-ink-2">{PHASE_LABEL[row.phase]} fuels</dt>
          <dd className="text-right">
            <span className="text-[14px] font-medium" style={{ color: VERDICT[row.verdict].color }}>
              {VERDICT[row.verdict].word}
            </span>
            <span className="mono block text-[11px] text-muted">
              {row.close} {row.close === 1 ? "test" : "tests"} nearby
            </span>
          </dd>
        </div>
      ))}
    </dl>
  );
}

function Answer({ answer, names }: { answer: AskAnswer; names: Record<string, string> }) {
  return (
    <p className="whitespace-pre-line">
      {splitCitations(answer.answer).map((part, index) =>
        index % 2 && names[part] ? (
          <Link key={index} href={`/investigations/${part}/`} className="mono rounded-[3px] border border-rule px-1.5 py-px text-[11px] text-ink-2 transition-colors hover:border-ink hover:text-ink">
            {names[part]} · {part}
          </Link>
        ) : (
          part
        ),
      )}
    </p>
  );
}

export function Guide({ data }: { data: GuideData }) {
  const pathname = usePathname() ?? "/";
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([{ id: 0, from: "orb", text: HELLO }]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [aloud, setAloud] = useState(false);
  const canListen = useSyncExternalStore(noSubscription, () => "SpeechRecognition" in window || "webkitSpeechRecognition" in window, () => false);
  const nextId = useRef(1);
  const log = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const recognizer = useRef<Recognizer | null>(null);

  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight });
  }, [messages, busy, open]);

  useEffect(() => {
    if (!open) return;
    input.current?.focus();
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  useEffect(
    () => () => {
      recognizer.current?.stop();
      window.speechSynthesis?.cancel();
    },
    [],
  );

  function say(text: string) {
    if (!aloud || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(text.replace(/PSI-\d+/g, "").replace(/\*\*/g, "")));
  }

  function add(message: Omit<Extract<Message, { from: "orb" }>, "id" | "from">) {
    setMessages((list) => [...list, { id: nextId.current++, from: "orb", ...message }]);
  }

  async function send(raw: string) {
    const text = raw.trim();
    if (busy || text.length < 3) return;
    setDraft("");
    setMessages((list) => [...list, { id: nextId.current++, from: "you", text }]);
    const local = localReply(text, pathname, data);
    if (local) {
      add(local);
      say(local.text);
      return;
    }
    setBusy(true);
    try {
      const answer = await ask(text);
      add({ answer });
      say(answer.answer);
    } catch (error) {
      add({ error: (error as Error).message });
    }
    setBusy(false);
  }

  function listen() {
    if (listening) {
      recognizer.current?.stop();
      return;
    }
    const speech = newRecognizer();
    if (!speech) return;
    recognizer.current = speech;
    speech.lang = "en-US";
    speech.interimResults = false;
    speech.onresult = (event) => void send(event.results[0]?.[0]?.transcript ?? "");
    speech.onend = () => setListening(false);
    speech.onerror = () => setListening(false);
    setListening(true);
    speech.start();
  }

  function toggleAloud() {
    if (aloud) window.speechSynthesis?.cancel();
    setAloud(!aloud);
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void send(draft);
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col items-end gap-3">
      <AnimatePresence>
        {open && (
          <motion.section
            role="dialog"
            aria-label="Orb, the guide"
            initial={{ opacity: 0, y: 12, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ duration: 0.18 }}
            className="panel flex max-h-[min(620px,calc(100svh-104px))] w-[min(400px,calc(100vw-32px))] origin-bottom-right flex-col overflow-hidden"
          >
            <header className="flex items-center gap-3 border-b border-rule px-4 py-3">
              <Orb size={36} busy={busy} />
              <div className="mr-auto leading-tight">
                <p className="text-[15px] font-medium">Orb</p>
                <p className="text-[12px] text-muted">Guide to NASA&apos;s fire record</p>
              </div>
              <button type="button" onClick={toggleAloud} aria-pressed={aloud} aria-label={aloud ? "Stop reading answers aloud" : "Read answers aloud"} title={aloud ? "Stop reading answers aloud" : "Read answers aloud"} className={`${ICON} ${aloud ? "border-accent text-accent" : ""}`}>
                <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M2.5 6.2v3.6h2.4L8 12.4V3.6L4.9 6.2z" />
                  {aloud ? <path d="M10.6 5.6a3.4 3.4 0 010 4.8M12.6 3.8a6 6 0 010 8.4" /> : <path d="M10.8 6.3l3 3.4m0-3.4l-3 3.4" />}
                </svg>
              </button>
              <button type="button" onClick={() => setOpen(false)} aria-label="Close the guide" title="Close the guide" className={ICON}>
                <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                  <path d="M4 4l8 8M12 4l-8 8" />
                </svg>
              </button>
            </header>

            <div ref={log} aria-live="polite" className="flex-1 space-y-3 overflow-y-auto px-4 py-4 text-[14px] leading-relaxed">
              {messages.map((message) =>
                message.from === "you" ? (
                  <p key={message.id} className="ml-auto w-fit max-w-[85%] rounded-[6px] bg-ink px-3 py-2 text-paper">
                    {message.text}
                  </p>
                ) : (
                  <div key={message.id} className="max-w-[92%]">
                    {message.text && <p>{message.text}</p>}
                    {message.habitat && <HabitatCard habitat={message.habitat} />}
                    {message.answer && <Answer answer={message.answer} names={data.names} />}
                    {message.error && <p style={{ color: "var(--signal)" }}>{message.error}</p>}
                    {message.link && (
                      <Link href={message.link.href} onClick={() => setOpen(false)} className="btn btn-primary mt-3 !h-10 !text-[15px]">
                        {message.link.label}
                      </Link>
                    )}
                  </div>
                ),
              )}
              {busy && <p className="text-muted">Reading NASA&apos;s records. The first answer can take a minute.</p>}
              {messages.length === 1 && (
                <ul className="space-y-1.5 pt-1">
                  {suggestionsFor(pathname).map((suggestion) => (
                    <li key={suggestion}>
                      <button type="button" onClick={() => void send(suggestion)} className="w-full rounded-[4px] border border-rule px-3 py-2 text-left text-[13px] text-ink-2 transition-[color,border-color,transform] hover:border-rule-strong hover:text-ink active:translate-y-px">
                        {suggestion}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <form onSubmit={onSubmit} className="flex items-center gap-2 border-t border-rule p-3">
              <label htmlFor="orb-question" className="sr-only">
                Question for Orb
              </label>
              <input
                id="orb-question"
                ref={input}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                maxLength={500}
                placeholder={listening ? "Listening" : "Ask about a test, a fuel or a habitat"}
                className="h-9 min-w-0 flex-1 rounded-[4px] border border-rule bg-paper px-3 text-[14px] placeholder:text-muted"
              />
              {canListen && (
                <button type="button" onClick={listen} aria-pressed={listening} aria-label={listening ? "Stop listening" : "Speak your question"} title={listening ? "Stop listening" : "Speak your question"} className={`${ICON} h-9 w-9 ${listening ? "border-signal text-signal" : ""}`}>
                  <svg viewBox="0 0 16 16" width="15" height="15" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                    <rect x="6" y="2" width="4" height="7.5" rx="2" />
                    <path d="M3.6 7.6a4.4 4.4 0 008.8 0M8 12v2.2" />
                  </svg>
                </button>
              )}
              <button type="submit" disabled={busy || draft.trim().length < 3} className="inline-flex h-9 items-center rounded-[4px] bg-ink px-3.5 text-[13px] font-medium text-paper transition-[transform,opacity] hover:-translate-y-px active:translate-y-px disabled:pointer-events-none disabled:opacity-40">
                Send
              </button>
            </form>
          </motion.section>
        )}
      </AnimatePresence>

      <button
        type="button"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-label={open ? "Close Orb, the guide" : "Ask Orb, the guide"}
        className="orb-launcher flex h-14 items-center gap-2 rounded-full border border-rule-strong bg-surface py-1 pl-1.5 pr-4 text-[13px] font-medium shadow-[var(--shadow)] transition-transform hover:-translate-y-0.5 active:translate-y-0"
      >
        <Orb size={44} busy={busy} />
        <span>{open ? "Close" : "Ask Orb"}</span>
      </button>
    </div>
  );
}
