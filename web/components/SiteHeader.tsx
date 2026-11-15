"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { AmbientSound } from "./AmbientSound";
import { Logo } from "./Logo";
import { JOURNEY } from "@/lib/journey";

const NAV = JOURNEY.map((stage) => ({ href: stage.path, label: stage.nav }));

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname.startsWith(href.replace(/\/$/, ""));
}

export function SiteHeader() {
  const pathname = usePathname() ?? "/";
  return (
    <header className="sticky top-0 z-40 border-b border-rule bg-paper/85 backdrop-blur-md supports-[backdrop-filter]:bg-paper/65">
      <div className="mx-auto flex h-14 max-w-[1240px] items-center gap-6 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5" aria-label="Flame in Freefall home">
          <Logo />
          <span className="leading-none">
            <span className="display block text-[19px] leading-none">Flame in Freefall</span>
            <span className="eyebrow block pt-1 text-[11px]">PSI · Combustion</span>
          </span>
        </Link>
        <nav aria-label="Main" className="hidden flex-1 items-center gap-0.5 xl:flex">
          {NAV.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`mono relative rounded-[2px] px-2.5 py-2 text-[11.5px] uppercase tracking-[0.1em] transition-colors ${active ? "text-ink" : "text-ink-2 hover:text-accent"}`}
              >
                {item.label}
                {active && (
                  <motion.span layoutId="nav-underline" className="absolute inset-x-2.5 -bottom-[11px] h-[2px] bg-accent" transition={{ type: "spring", stiffness: 500, damping: 40 }} />
                )}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <AmbientSound />
        </div>
      </div>
      <nav aria-label="Main mobile" className="flex gap-1 overflow-x-auto border-t border-rule px-3 py-1.5 [scrollbar-width:none] xl:hidden">
        {NAV.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              ref={active ? (el) => el?.scrollIntoView({ inline: "nearest", block: "nearest" }) : undefined}
              className={`mono whitespace-nowrap rounded-[2px] px-2.5 py-1.5 text-[11.5px] uppercase tracking-[0.08em] ${active ? "bg-accent text-accent-ink" : "text-ink-2"}`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
