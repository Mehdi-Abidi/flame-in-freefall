import type { Metadata } from "next";
import { Suspense } from "react";
import { RankBoard } from "@/components/RankBoard";
import { SectionHeader } from "@/components/Section";
import { loadDataset } from "@/lib/data";

export const metadata: Metadata = { title: "Rank for a habitat" };

export default function RankPage() {
  const data = loadDataset();
  return (
    <div className="mx-auto max-w-[1240px] px-4 pt-12 sm:px-6">
      <h1 className="mb-6 text-[34px] font-semibold tracking-[-0.02em] sm:text-[44px]">Rank for a habitat</h1>
      <SectionHeader title="How to read it">
        Pick where the crew will live and how much you care about preventing, detecting or putting out a fire. Every investigation is scored from
        0 to 100 from four visible parts, so you can always see why something ranks first. Move a slider and the list re-orders. Arrows show
        movement against the balanced ranking.
      </SectionHeader>
      <Suspense fallback={<p className="text-ink-2">Loading ranking…</p>}>
        <RankBoard investigations={data.investigations} scenarios={data.scenarios} componentWeights={data.componentWeights} />
      </Suspense>
    </div>
  );
}
