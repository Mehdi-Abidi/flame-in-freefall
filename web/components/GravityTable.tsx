import type { GravityRow } from "@/lib/types";

function burned(text: string): "full" | "partial" | "none" | "unknown" {
  const t = text.toLowerCase();
  if (!t) return "unknown";
  if (t.includes("complete")) return "full";
  if (t.startsWith("~ 0") || t === "0") return "none";
  return "partial";
}

const MARK: Record<string, { label: string; className: string }> = {
  full: { label: "burned fully", className: "bg-ink text-paper" },
  partial: { label: "partly", className: "border border-ink-2 text-ink" },
  none: { label: "barely", className: "border border-dashed border-rule-strong text-muted" },
  unknown: { label: "not recorded", className: "text-muted" },
};

function Outcome({ text }: { text: string }) {
  const kind = burned(text);
  return (
    <span className="inline-flex flex-col gap-1">
      <span className={`mono inline-block w-fit rounded-[3px] px-1.5 py-0.5 text-[10.5px] uppercase tracking-[0.08em] ${MARK[kind].className}`}>{MARK[kind].label}</span>
      <span className="mono text-[11.5px] text-muted">{text || "n/a"}</span>
    </span>
  );
}

export function GravityTable({ rows }: { rows: GravityRow[] }) {
  return (
    <div className="overflow-x-auto rounded-[6px] border border-rule bg-surface">
      <table className="w-full min-w-[640px] border-collapse text-[13.5px]">
        <caption className="sr-only">SAFFIRE-II samples burned in microgravity compared with the same samples in 1 g ground tests</caption>
        <thead>
          <tr className="eyebrow border-b border-rule text-left">
            <th className="px-4 py-3 font-normal">Sample</th>
            <th className="px-4 py-3 font-normal">Material</th>
            <th className="px-4 py-3 font-normal">Flow</th>
            <th className="px-4 py-3 font-normal">In microgravity</th>
            <th className="px-4 py-3 font-normal">On Earth (1 g)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.sample} className="border-b border-rule last:border-0">
              <td className="mono px-4 py-3 text-ink-2">{row.sample}</td>
              <td className="px-4 py-3">
                {row.material}
                <span className="mono block text-[11.5px] text-muted">{row.thickness}</span>
              </td>
              <td className="px-4 py-3 text-ink-2">{row.flowDirection.toLowerCase()}</td>
              <td className="px-4 py-3">
                <Outcome text={row.microBurn} />
              </td>
              <td className="px-4 py-3">
                <Outcome text={row.oneGBurn} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
