import type { Metadata } from "next";
import { CabinLab } from "@/components/CabinLab";
import { loadDataset } from "@/lib/data";
import { loadLabData } from "@/lib/labData";

export const metadata: Metadata = { title: "Cabin lab" };

export default function LabPage() {
  const data = loadDataset();
  const lab = loadLabData();
  const names = Object.fromEntries(data.investigations.map((i) => [i.accession, i.name]));
  const groundRow = data.gravity.find((row) => row.sample === "2-1") ?? null;
  return (
    <div className="mx-auto max-w-[1240px] px-4 pt-12 sm:px-6">
      <CabinLab tests={lab.tests} smoke={lab.smoke} scenarios={data.scenarios} names={names} groundRow={groundRow} />
    </div>
  );
}
