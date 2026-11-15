import { stageLabel } from "@/lib/journey";
import type { Metadata } from "next";
import { InvestigationExplorer } from "@/components/InvestigationExplorer";
import { PageIntro } from "@/components/Section";
import { loadDataset } from "@/lib/data";

export const metadata: Metadata = { title: "Investigations" };

export default function InvestigationsPage() {
  const data = loadDataset();
  return (
    <div className="mx-auto max-w-[1240px] px-4 pt-12 sm:px-6">
      <PageIntro kicker={`${stageLabel("/investigations/")} · Investigations`} title="The 24 investigations">
        Every combustion investigation in NASA&apos;s PSI repository, in plain words. Summaries were drafted by an open model from NASA&apos;s text.
      </PageIntro>
      <InvestigationExplorer investigations={data.investigations} />
    </div>
  );
}
