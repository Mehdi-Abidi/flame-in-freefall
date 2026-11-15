"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { Logo } from "./Logo";
import { ThemeToggle } from "./ThemeToggle";

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/rank/", label: "Rank" },
  { href: "/investigations/", label: "Investigations" },
  { href: "/compare/", label: "Compare" },
  { href: "/ask/", label: "Ask" },
  { href: "/method/", label: "Method" },
];

function isActive(pathname: string, href: string) {
  if (href === "/") return pathname === "/";
  return pathname.startsWith(href.replace(/\/$/, ""));
}

export function SiteHeader() {
  const pathname = usePathname() ?? "/";
  return (
    <header className="sticky top-0 z-40 border-b border-rule bg-paper/85 backdrop-blur-md supports-[backdrop-filter]:bg-paper/70">
      <div className="mx-auto flex h-14 max-w-[1240px] items-center gap-6 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2.5" aria-label="Flame in Freefall home">
          <Logo />
          <span className="leading-none">
            <span className="block text-[13px] font-semibold tracking-tight">Flame in Freefall</span>
            <span className="eyebrow block pt-1 text-[11px]">PSI · Combustion</span>
          </span>
        </Link>
        <nav aria-label="Main" className="hidden flex-1 items-center gap-1 md:flex">
          {NAV.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`relative rounded-[4px] px-3 py-2 text-[13px] transition-colors ${active ? "text-ink" : "text-ink-2 hover:text-ink"}`}
              >
                {item.label}
                {active && (
                  <motion.span layoutId="nav-underline" className="absolute inset-x-3 -bottom-[11px] h-[2px] bg-accent" transition={{ type: "spring", stiffness: 500, damping: 40 }} />
                )}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <span className="mono hidden text-[11px] text-muted lg:inline">NASA SPACE APPS 2026</span>
          <ThemeToggle />
        </div>
      </div>
      <nav aria-label="Main mobile" className="flex gap-1 overflow-x-auto border-t border-rule px-3 py-1.5 [scrollbar-width:none] md:hidden">
        {NAV.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              // Keep the current page in view when the row is wider than the phone.
              ref={active ? (el) => el?.scrollIntoView({ inline: "nearest", block: "nearest" }) : undefined}
              className={`whitespace-nowrap rounded-[4px] px-2.5 py-1.5 text-[12.5px] ${active ? "bg-ink text-paper" : "text-ink-2"}`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
