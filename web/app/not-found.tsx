import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto flex max-w-[1240px] flex-col items-start px-4 py-24 sm:px-6">
      <p className="eyebrow">Error 404 · no data at these coordinates</p>
      <h1 className="mt-4 max-w-[18ch] text-[44px] font-semibold leading-tight tracking-[-0.02em]">This page burned out before it reached orbit.</h1>
      <p className="mt-4 max-w-xl text-[16px] text-ink-2">The link may be old, or the investigation ID may be mistyped. All 24 investigations are listed in the catalogue.</p>
      <div className="mt-8 flex gap-3">
        <Link href="/" className="rounded-[4px] bg-accent px-4 py-2.5 text-[14px] font-medium text-accent-ink">
          Back to overview
        </Link>
        <Link href="/investigations/" className="rounded-[4px] border border-rule-strong px-4 py-2.5 text-[14px]">
          Browse investigations
        </Link>
      </div>
    </div>
  );
}
