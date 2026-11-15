import { stageLabel } from "@/lib/journey";
import type { Metadata } from "next";
import { Suspense } from "react";
import { CompareView } from "@/components/CompareView";
import { PageIntro } from "@/components/Section";
import { loadDataset } from "@/lib/data";

export const metadata: Metadata = { title: "Compare" };

export default function ComparePage() {
  const data = loadDataset();
  return (
    <div className="mx-auto max-w-[1240px] px-4 pt-12 sm:px-6">
      <PageIntro kicker={`${stageLabel("/compare/")} · Compare`} title="Compare">
        Put up to four investigations side by side. Differences are marked.
      </PageIntro>
      <Suspense fallback={<p className="text-ink-2">Loading…</p>}>
        <CompareView investigations={data.investigations} />
      </Suspense>
    </div>
  );
}
