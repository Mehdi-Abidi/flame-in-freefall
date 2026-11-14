import type { Metadata } from "next";
import { Suspense } from "react";
import { RankBoard } from "@/components/RankBoard";
import { PageIntro } from "@/components/Section";
import { loadDataset } from "@/lib/data";

export const metadata: Metadata = { title: "Rank for a habitat" };

export default function RankPage() {
  const data = loadDataset();
  return (
    <div className="mx-auto max-w-[1240px] px-4 pt-12 sm:px-6">
      <PageIntro title="Rank for a habitat">
        Pick where the crew will live and how much you care about preventing, detecting or putting out a fire. Every investigation is scored from
        0 to 100 from four visible parts, so you can always see why something ranks first. Move a slider and the list re-orders. Arrows show
        movement against the balanced ranking.
      </PageIntro>
      <Suspense fallback={<p className="text-ink-2">Loading ranking…</p>}>
        <RankBoard investigations={data.investigations} scenarios={data.scenarios} componentWeights={data.componentWeights} />
      </Suspense>
    </div>
  );
}
