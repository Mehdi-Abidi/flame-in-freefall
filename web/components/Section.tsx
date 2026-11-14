import type { ReactNode } from "react";

export function SectionHeader({ code, title, children }: { code: string; title: string; children?: ReactNode }) {
  return (
    <div className="mb-6 grid gap-3 md:grid-cols-[200px_1fr] md:gap-10">
      <p className="eyebrow pt-1.5">
        <span className="text-accent">§{code}</span> · {title}
      </p>
      <div className="max-w-3xl text-[15px] leading-relaxed text-ink-2">{children}</div>
    </div>
  );
}

export function StatTile({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <div className="ticks border border-rule bg-surface px-5 py-4">
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-[44px] font-semibold leading-none tracking-tight">{value}</p>
      <p className="mt-2 text-[13px] text-ink-2">{note}</p>
    </div>
  );
}
