export interface EarthTheme {
  id: string;
  title: string;
  intro: string;
  accessions: string[];
}

export const EARTH_THEMES: EarthTheme[] = [
  {
    id: "smoke",
    title: "Smoke detectors for places where air barely moves",
    intro:
      "Four investigations measured or modelled smoke in microgravity, where particles grow and drift differently. Their NASA records name better smoke detectors, including for submarines and underwater labs.",
    accessions: ["PSI-47", "PSI-102", "PSI-101", "PSI-115"],
  },
  {
    id: "confined",
    title: "Fire safety in mines, aircraft and submarines",
    intro:
      "Closed spaces with forced ventilation behave more like a spacecraft than an open room. The large-fire, extinction and flame-spread studies name these settings, plus suppression systems and material screening.",
    accessions: ["PSI-98", "PSI-99", "PSI-100", "PSI-69", "PSI-25", "PSI-62", "PSI-20"],
  },
  {
    id: "engines",
    title: "Cleaner engines, burners and power plants",
    intro:
      "Without buoyancy, flames are simpler to model, so the gas and liquid flame studies feed combustion models used on Earth. Their records name more efficient engines and lower emissions.",
    accessions: ["PSI-10", "PSI-22", "PSI-23", "PSI-39", "PSI-159", "PSI-68", "PSI-106", "PSI-107", "PSI-60", "PSI-117"],
  },
];

export function benefitText(text: string): string {
  const first = text.split("; ")[0].trim().replace(/\.$/, "");
  return first.charAt(0).toUpperCase() + first.slice(1);
}
