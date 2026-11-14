import type { Metadata } from "next";
import { InvestigationExplorer } from "@/components/InvestigationExplorer";
import { PageIntro } from "@/components/Section";
import { loadDataset } from "@/lib/data";

export const metadata: Metadata = { title: "Investigations" };

export default function InvestigationsPage() {
  const data = loadDataset();
  return (
    <div className="mx-auto max-w-[1240px] px-4 pt-12 sm:px-6">
      <PageIntro title="The 24 investigations">
        Every combustion investigation in NASA&apos;s Physical Sciences Informatics repository. Summaries were drafted by an open model from
        NASA&apos;s own text and checked against the test tables. Colour dots show the fuel phases each one burned.
      </PageIntro>
      <InvestigationExplorer investigations={data.investigations} />
    </div>
  );
}
