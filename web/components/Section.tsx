import type { ReactNode } from "react";

export function PageIntro({ title, kicker, children }: { title: string; kicker?: string; children?: ReactNode }) {
  return (
    <header className="hero-enter mb-10">
      {kicker && <p className="eyebrow mb-3 text-accent">{kicker}</p>}
      <h1 className="display text-[52px] sm:text-[80px]">{title}</h1>
      {children && <p className="mt-4 max-w-[52ch] text-[16px] leading-relaxed text-ink-2">{children}</p>}
    </header>
  );
}

export function SectionHeader({ title, step, children }: { title: string; step?: string; children?: ReactNode }) {
  return (
    <div className="mb-6">
      {step && <p className="eyebrow mb-2 text-accent">{step}</p>}
      <h2 className="display text-[36px] sm:text-[46px]">{title}</h2>
      {children && <div className="mt-3 max-w-[60ch] text-[15px] leading-relaxed text-ink-2">{children}</div>}
    </div>
  );
}
