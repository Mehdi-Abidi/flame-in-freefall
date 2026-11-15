import { describe, expect, it } from "vitest";
import { loadDataset } from "./data";
import { EARTH_THEMES, benefitText } from "./earth";

describe("Back on Earth themes", () => {
  const data = loadDataset();
  const byAccession = new Map(data.investigations.map((i) => [i.accession, i]));
  const listed = EARTH_THEMES.flatMap((t) => t.accessions);

  it("lists every investigation whose NASA record names a use on Earth, exactly once", () => {
    const withBenefits = data.investigations.filter((i) => i.earthBenefits.length).map((i) => i.accession);
    expect([...listed].sort()).toEqual([...withBenefits].sort());
    expect(new Set(listed).size).toBe(listed.length);
  });

  it("only lists investigations that exist and have uses to show", () => {
    for (const accession of listed) expect(byAccession.get(accession)?.earthBenefits.length).toBeGreaterThan(0);
  });

  it("keeps each theme's intro true to the records it groups", () => {
    const text = (id: string) =>
      EARTH_THEMES.find((t) => t.id === id)!.accessions.flatMap((a) => byAccession.get(a)!.earthBenefits).join(" ").toLowerCase();
    expect(text("smoke")).toMatch(/smoke detect/);
    expect(text("smoke")).toMatch(/submarine/);
    expect(text("confined")).toMatch(/mines/);
    expect(text("confined")).toMatch(/suppression/);
    expect(text("engines")).toMatch(/engine/);
    expect(text("engines")).toMatch(/emission/);
  });

  it("drops a cut-off clause and capitalises", () => {
    expect(benefitText("advances understanding; delivers validate")).toBe("Advances understanding");
    expect(benefitText("mines")).toBe("Mines");
  });
});
