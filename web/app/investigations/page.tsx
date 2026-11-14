import type { Metadata } from "next";
import { InvestigationExplorer } from "@/components/InvestigationExplorer";
import { SectionHeader } from "@/components/Section";
import { loadDataset } from "@/lib/data";

export const metadata: Metadata = { title: "Investigations" };

export default function InvestigationsPage() {
  const data = loadDataset();
  return (
    <div className="mx-auto max-w-[1240px] px-4 pt-12 sm:px-6">
      <h1 className="mb-6 text-[34px] font-semibold tracking-[-0.02em] sm:text-[44px]">The 24 investigations</h1>
      <SectionHeader title="Catalogue">
        Every combustion investigation in NASA&apos;s Physical Sciences Informatics repository. Summaries were drafted by an open model from
        NASA&apos;s own text and checked against the test tables. Colour dots show the fuel phases each one burned.
      </SectionHeader>
      <InvestigationExplorer investigations={data.investigations} />
    </div>
  );
}
