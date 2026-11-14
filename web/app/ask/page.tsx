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
      <PageIntro title="Ask the PSI data">
        Ask a question in plain English. Answers come only from NASA PSI investigation records and test data, and every claim cites the
        investigation it came from. If the data does not cover it, the answer says so.
      </PageIntro>
      <AskChat names={names} />
    </div>
  );
}
