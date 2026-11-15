import type { ReactNode } from "react";

export function PageIntro({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <header className="mb-8">
      <h1 className="text-[36px] font-medium leading-[1.06] tracking-[-0.035em] sm:text-[48px]">{title}</h1>
      {children && <p className="mt-3 max-w-[60ch] text-[16px] leading-relaxed text-ink-2">{children}</p>}
    </header>
  );
}

export function SectionHeader({ title, step, children }: { title: string; step?: string; children?: ReactNode }) {
  return (
    <div className="mb-6">
      {step && <p className="eyebrow mb-2">{step}</p>}
      <h2 className="text-[26px] font-medium leading-tight tracking-[-0.02em]">{title}</h2>
      {children && <div className="mt-2 max-w-[60ch] text-[15px] leading-relaxed text-ink-2">{children}</div>}
    </div>
  );
}
