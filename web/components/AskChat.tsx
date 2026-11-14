"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { ask, splitCitations, type AskAnswer } from "@/lib/ask";

const EXAMPLES = [
  "Which diluent put out droplet flames at lower oxygen, CO2 or helium?",
  "What oxygen levels did BASS-II test?",
  "Which investigations studied flame spread over solid fuels?",
];

interface Turn {
  question: string;
  result?: AskAnswer;
  error?: string;
}

function Citation({ id, names }: { id: string; names: Record<string, string> }) {
  return (
    <Link
      href={`/investigations/${id}/`}
      className="mono rounded-[3px] border border-rule px-1.5 py-px text-[11px] text-ink-2 transition-colors hover:border-ink hover:text-ink"
    >
      {names[id]} · {id}
    </Link>
  );
}

function AnswerText({ text, names }: { text: string; names: Record<string, string> }) {
  return (
    <p className="whitespace-pre-line text-[15px] leading-relaxed">
      {splitCitations(text).map((part, i) => (i % 2 && names[part] ? <Citation key={i} id={part} names={names} /> : part))}
    </p>
  );
}

export function AskChat({ names }: { names: Record<string, string> }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(text: string) {
    const q = text.trim();
    if (busy || q.length < 3) return;
    setBusy(true);
    setQuestion("");
    setTurns((t) => [{ question: q }, ...t]);
    let done: Turn;
    try {
      done = { question: q, result: await ask(q) };
    } catch (error) {
      done = { question: q, error: (error as Error).message };
    }
    setTurns((t) => [done, ...t.slice(1)]);
    setBusy(false);
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    submit(question);
  }

  return (
    <div className="max-w-[760px]">
      <form onSubmit={onSubmit} className="flex flex-col gap-2 sm:flex-row">
        <label htmlFor="ask-input" className="sr-only">
          Your question
        </label>
        <input
          id="ask-input"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={500}
          placeholder="Ask about PSI combustion experiments"
          className="min-w-0 flex-1 rounded-[4px] border border-rule-strong bg-surface px-3 py-2.5 text-[15px] placeholder:text-muted"
        />
        <button
          type="submit"
          disabled={busy || question.trim().length < 3}
          className="rounded-[4px] bg-ink px-4 py-2.5 text-[14px] font-medium text-paper disabled:opacity-40"
        >
          {busy ? "Asking…" : "Ask"}
        </button>
      </form>

      {turns.length === 0 && (
        <div className="mt-6">
          <p className="eyebrow mb-2">Try</p>
          <ul className="flex flex-col gap-2">
            {EXAMPLES.map((example) => (
              <li key={example}>
                <button type="button" onClick={() => submit(example)} className="text-left text-[14px] text-ink-2 underline-offset-4 hover:text-ink hover:underline">
                  {example}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <ol className="mt-8 space-y-8" aria-live="polite">
        {turns.map((turn, index) => (
          <li key={turns.length - index} className="border-t border-rule pt-4">
            <p className="text-[15px] font-semibold">{turn.question}</p>
            <div className="mt-3">
              {turn.error ? (
                <p role="alert" className="text-[14px] text-accent">
                  {turn.error}
                </p>
              ) : !turn.result ? (
                <p className="text-[14px] text-ink-2">Searching the PSI data… The API sleeps when idle, so the first question can take up to a minute.</p>
              ) : (
                <>
                  <AnswerText text={turn.result.answer} names={names} />
                  {turn.result.sources.length > 0 && (
                    <details className="mt-3">
                      <summary className="cursor-pointer text-[12px] text-muted">
                        {turn.result.sources.length} passages searched
                      </summary>
                      <ul className="mt-2 space-y-2">
                        {turn.result.sources.map((source, i) => (
                          <li key={i} className="text-[13px] leading-relaxed text-ink-2">
                            <span className="mono text-[12px] text-muted">
                              {source.acronym} · {source.field}
                            </span>{" "}
                            {source.text}
                          </li>
                        ))}
                      </ul>
                    </details>
                  )}
                </>
              )}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
