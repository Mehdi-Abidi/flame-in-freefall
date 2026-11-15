import { stageLabel } from "@/lib/journey";
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
      <PageIntro kicker={`${stageLabel("/rank/")} · Rank`} title="Rank for a habitat">
        Pick a habitat and what matters most. All 24 investigations re-order live, and every score shows its parts.
      </PageIntro>
      <Suspense fallback={<p className="text-ink-2">Loading ranking…</p>}>
        <RankBoard investigations={data.investigations} scenarios={data.scenarios} componentWeights={data.componentWeights} />
      </Suspense>
    </div>
  );
}
