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
      <PageIntro title="Compare investigations">
        Put up to four investigations next to each other. Attributes that differ are marked, so you can see at a glance how FLEX-2 changed the
        FLEX recipe, or how BASS-II extended BASS.
      </PageIntro>
      <Suspense fallback={<p className="text-ink-2">Loading…</p>}>
        <CompareView investigations={data.investigations} />
      </Suspense>
    </div>
  );
}
