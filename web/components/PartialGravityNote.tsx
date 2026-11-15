import Link from "next/link";
import type { Investigation } from "@/lib/types";

const CHALLENGE_URL = "https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/";

function listOf(items: string[]): string {
  if (items.length < 2) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

export function PartialGravityNote({ efield, efieldOnMap }: { efield?: Investigation; efieldOnMap: boolean }) {
  const count = efield ? (efield.nTests > 0 ? `${efield.nTests} tests` : `${efield.nRecords} test days`) : "";
  const gasOnly = efield ? efield.phases.length === 1 && efield.phases[0] === "gas" : false;
  const noAtmosphere = efield ? !efield.o2Range && !efield.kpaRange && !efieldOnMap : false;

  return (
    <div className="mt-12">
      <h3 id="partial-gravity" className="text-[19px] font-semibold leading-snug">
        Partial gravity is the missing column
      </h3>
      <div className="mt-5 grid gap-x-10 gap-y-8 md:grid-cols-3">
        <div className="border-t-2 border-ink pt-4">
          <h4 className="text-[16px] font-semibold">No data in PSI yet</h4>
          <p className="mt-2 text-[13.5px] leading-relaxed text-ink-2">
            PSI holds no partial-gravity combustion data yet, so nothing on this site was measured at lunar or Martian gravity. The challenge says
            such data is expected, for example from the Lunar-g Combustion Investigation (LUCI) and the Flammability of Materials on the Moon (FM2)
            experiment.
          </p>
        </div>

        <div className="border-t-2 border-ink pt-4">
          <h4 className="text-[16px] font-semibold">E-FIELD mimicked it</h4>
          <p className="mt-2 text-[13.5px] leading-relaxed text-ink-2">
            ACME&apos;s E-FIELD Flames experiment mimicked partial gravity through the effect of an electric field on the ions that occur
            naturally in flames.
            {efield && (
              <>
                {" "}
                PSI lists {count} of {efield.fuels.length ? `${listOf(efield.fuels)} flames` : "flames"} for it.
                {gasOnly && " Those are gas flames, not cabin materials."}
                {noAtmosphere && " Its table records no oxygen or pressure, so it has no points on the gap map."}
              </>
            )}
          </p>
          {efield && (
            <Link
              href={`/investigations/${efield.accession}/`}
              className="mono mt-3 inline-block rounded-[3px] border border-rule px-1.5 py-px text-[11px] text-ink-2 transition-colors hover:border-ink hover:text-ink"
            >
              {efield.name} · {efield.accession}
            </Link>
          )}
        </div>

        <div className="border-t-2 border-ink pt-4">
          <h4 className="text-[16px] font-semibold">Until then, two bounds</h4>
          <p className="mt-2 text-[13.5px] leading-relaxed text-ink-2">
            Microgravity and normal-gravity results could bound what occurs at the gravity levels in between. That is why the SAFFIRE-II samples
            above are shown under both.
          </p>
        </div>
      </div>
      <p className="mono mt-6 text-[12px] text-muted">
        Source: the partial-gravity notes in{" "}
        <a className="link-underline text-ink-2" href={CHALLENGE_URL}>
          the challenge text
        </a>
        . Counts come from NASA&apos;s PSI tables.
      </p>
    </div>
  );
}
