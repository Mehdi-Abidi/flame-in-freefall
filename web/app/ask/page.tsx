import { stageLabel } from "@/lib/journey";
import type { Metadata } from "next";
import { AskChat } from "@/components/AskChat";
import { PageIntro } from "@/components/Section";
import { loadDataset } from "@/lib/data";

export const metadata: Metadata = { title: "Ask" };

export default function AskPage() {
  const data = loadDataset();
  const names = Object.fromEntries(data.investigations.map((i) => [i.accession, i.name]));
  return (
    <div className="mx-auto max-w-[1240px] px-4 pt-12 sm:px-6">
      <PageIntro kicker={`${stageLabel("/ask/")} · Ask`} title="Ask the record">
        Plain-English questions, answered only from NASA&apos;s PSI records, with citations.
      </PageIntro>
      <AskChat names={names} />
    </div>
  );
}
