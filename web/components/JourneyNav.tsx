"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { JOURNEY, stageIndex } from "@/lib/journey";

/** The way on from every page: where you are in the nine stages, the one before and the one after. */
export function JourneyNav() {
  const pathname = usePathname() ?? "/";
  if (pathname === "/") return null;
  const index = stageIndex(pathname);
  const previous = JOURNEY[index - 1];
  const next = JOURNEY[index + 1] ?? JOURNEY[0];
  return (
    <nav aria-label="Next stage" className="mx-auto mt-24 w-full max-w-[1240px] px-4 sm:px-6">
      <div className="mb-4 flex items-center gap-3">
        <p className="eyebrow">
          Stage {index + 1} of {JOURNEY.length}
        </p>
        <div className="flex flex-1 gap-1" aria-hidden="true">
          {JOURNEY.map((stage, i) => (
            <span key={stage.path} className={`h-[3px] flex-1 ${i <= index ? "bg-accent" : "bg-rule"}`} />
          ))}
        </div>
      </div>
      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        {previous ? (
          <Link href={previous.path} className="panel bento p-5">
            <span className="eyebrow">Back</span>
            <span className="display mt-2 text-[26px] text-ink-2">{previous.label}</span>
          </Link>
        ) : (
          <span />
        )}
        <Link href={next.path} className="panel bento p-5">
          <span className="eyebrow text-accent">Next stage</span>
          <span className="display mt-2 flex items-center gap-3 text-[34px] sm:text-[44px]">
            {next.label}
            <span className="arrow text-accent" aria-hidden="true">
              →
            </span>
          </span>
          <span className="mt-2 text-[14px] text-ink-2">{next.line}</span>
        </Link>
      </div>
    </nav>
  );
}
