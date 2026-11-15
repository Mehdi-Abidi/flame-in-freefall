import { burnExtent, referencedNotes, type BurnExtent } from "@/lib/gravity";
import type { GravityNote, GravityRow } from "@/lib/types";

const CAPTION = "SAFFIRE-II samples burned in microgravity compared with the same samples in 1 g ground tests";

const MARK: Record<Exclude<BurnExtent, "unknown">, { label: string; className: string }> = {
  full: { label: "burned fully", className: "bg-ink text-paper" },
  partial: { label: "partly", className: "border border-ink-2 text-ink" },
  none: { label: "barely", className: "border border-dashed border-rule-strong text-muted" },
};

function Outcome({ text }: { text: string }) {
  const kind = burnExtent(text);
  if (kind === "unknown") return <span className="mono text-[12px] text-muted">{text || "not recorded"}</span>;
  return (
    <span className="inline-flex flex-col gap-1">
      <span className={`mono inline-block w-fit rounded-[3px] px-1.5 py-0.5 text-[11px] uppercase tracking-[0.08em] ${MARK[kind].className}`}>{MARK[kind].label}</span>
      <span className="mono text-[12px] text-muted">{text}</span>
    </span>
  );
}

export function GravityTable({ rows, notes = [] }: { rows: GravityRow[]; notes?: GravityNote[] }) {
  const shown = referencedNotes(rows, notes);
  return (
    <>
      <ul aria-label={CAPTION} className="divide-y divide-[color:var(--rule)] rounded-[6px] border border-rule bg-surface md:hidden">
        {rows.map((row) => (
          <li key={row.sample} className="px-4 py-3.5">
            <p className="text-[14px]">
              <span className="mono mr-2 text-[12.5px] text-ink-2">{row.sample}</span>
              {row.material}
            </p>
            <p className="mono mt-0.5 text-[12px] text-muted">
              {row.thickness} · {row.flowDirection.toLowerCase()} flow
            </p>
            <dl className="mt-3 grid grid-cols-2 gap-3">
              <div>
                <dt className="eyebrow mb-1.5">Microgravity</dt>
                <dd>
                  <Outcome text={row.microBurn} />
                </dd>
              </div>
              <div>
                <dt className="eyebrow mb-1.5">Earth (1 g)</dt>
                <dd>
                  <Outcome text={row.oneGBurn} />
                </dd>
              </div>
            </dl>
          </li>
        ))}
      </ul>

      <div className="hidden overflow-x-auto rounded-[6px] border border-rule bg-surface md:block">
        <table className="w-full min-w-[640px] border-collapse text-[13.5px]">
          <caption className="sr-only">{CAPTION}</caption>
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
                  <span className="mono block text-[12px] text-muted">{row.thickness}</span>
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
      {shown.length > 0 && (
        <ol className="mt-3 space-y-1 text-[12px] leading-relaxed text-muted">
          {shown.map((note) => (
            <li key={note.note}>
              Note {note.note}: {note.text}
            </li>
          ))}
        </ol>
      )}
    </>
  );
}
