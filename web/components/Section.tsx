import type { ReactNode } from "react";

export function SectionHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-6">
      <h2 className="text-[24px] font-semibold leading-tight tracking-[-0.01em]">{title}</h2>
      {children && <div className="mt-2 max-w-[68ch] text-[15px] leading-relaxed text-ink-2">{children}</div>}
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
