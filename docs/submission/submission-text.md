# Submission text (draft, F6)

Draft for the Space Apps 2026 project page. Taha polishes it in T5. Check every field against the 2026 Project Submission Guide before pasting it in. Facts come from the README, the Method page and `data/processed/`.

## Project title

Flame in Freefall: fire safety answers from NASA's microgravity combustion data

## Short summary

Lunar habitats are expected to run at 30% oxygen or more, yet no solid-material fire test in NASA's Physical Sciences Informatics (PSI) repository ran above 22.2%. Flame in Freefall turns PSI's 24 combustion investigations into a fire safety dashboard. You pick a habitat (ISS, lunar base, pressurized rover, Mars habitat or spacesuit) and see which experiments matter for it, which conditions were actually tested and where the data runs out. You can also ask questions in plain English and get answers that cite NASA's records.

## Project links

- Live dashboard: https://mehdi-abidi.github.io/flame-in-freefall/
- Source code: https://github.com/Mehdi-Abidi/flame-in-freefall
- Public API: https://flame-in-freefall-api.onrender.com (docs at `/docs`)

## Detailed description

### What it does

NASA has flown dozens of fire experiments on the International Space Station. Their results sit in PSI as 24 investigations, 21 experimental tables and more than 82,000 raw files. That is hard to search when you are designing a habitat and need to know how a fabric burns at 30% oxygen. The dashboard answers that in six views:

- **Overview** shows the headline gap. An oxygen ruler compares the oxygen measured for each fuel phase with the lunar band. A gap map plots every test by oxygen and pressure against the habitat boxes. A SAFFIRE-II panel compares the same materials burned in microgravity and at 1 g.
- **Rank** scores all 24 investigations for the chosen habitat. Sliders weight the three fire-safety pillars (prevention, detection, suppression), and the list re-orders live. Each row shows its score parts and a two-sentence reason. The view lives in the URL, so it can be shared.
- **Investigations** lets you search and filter all 24. Each one has its own page with a plain summary, the conditions tested, its tests on the map and every publication, all linked to the NASA record.
- **Compare** puts up to four investigations side by side and marks what differs, for example how FLEX-2 changed the FLEX recipe.
- **Back on Earth** groups the uses on Earth that 21 investigations name in their NASA records: smoke detectors for submarines and underwater labs, fire safety in mines, aircraft and submarines, and cleaner engines and power plants.
- **Ask** answers questions such as "Which diluent put out droplet flames at lower oxygen, CO2 or helium?" Every answer cites PSI accession numbers. If the data does not cover a question, the answer says so.

Three findings stand out in the data:

- No solid-material fire test in PSI ran above 22.2% oxygen. That covers 140 tests across BASS-II, SAFFIRE-I and SAFFIRE-II.
- Only 20 tests sit at lunar-base conditions (30% oxygen or more at 70 kPa or less), and all of them are gas flames from ACME CFI-G.
- Gravity changes which material is worse. In SAFFIRE-II, thin silicone sheets burned completely at 1 g but barely burned in microgravity, while a cotton-fiberglass fabric burned its full 29 cm length in both.

### How it works

1. **Fetch.** The PSI search API lists the 24 combustion investigations. We download their metadata and the experimental tables, under 1 MB in total. The 16 TB of raw video and sensor files stay on NASA's servers and are linked, never copied.
2. **Normalize.** 21 tables in different units (mmHg, atm, bar, percent, mole fraction) become one table of 2,127 test rows. Every oxygen and pressure value carries a tag saying whether it was measured, planned or assumed, so an assumed cabin value is never shown as a test condition.
3. **Extract.** An open-weight model (GPT-OSS 20B on Groq) reads NASA's text for each investigation and pulls out fuels, sample geometry, sensors and fire-safety pillars. Facts the tables already prove are given to it as ground truth. Which conditions varied and which stayed fixed is computed from the tables, not the model, and anything the model names that is not in the source is flagged.
4. **Rank.** A deterministic score, with no AI involved, rates each investigation for each habitat. It has four parts: condition fit 35%, pillar match 25%, material relevance 20% and data richness 20%. The same formula runs in Python for the data files and in the browser for the sliders, and a test proves all 120 scores agree.
5. **Explain.** The model writes the ranking reasons and one insight brief per pillar, using only facts the code hands it. Code checks every number, rank and citation. A reply that fails is sent back once with its problems, and if it fails again a fact-only template is used and labelled as such.
6. **Ask.** A keyword search (BM25) finds the five most relevant passages from NASA's text and from summaries built from the test data. The model must answer only from those passages and cite their accession numbers. An answer without valid citations is replaced by "Not covered in PSI data."

All checks run automatically on every change, in GitHub Actions.

### Benefits

- **Habitat designers** see in seconds which experiments come closest to their cabin's oxygen and pressure, and how far the evidence falls short.
- **Fire modelers** get one clean test table in common units, filterable by oxygen, pressure and investigation, and downloadable as CSV from the API.
- **Researchers and planners** see where data is missing, such as solids above 22% oxygen and partial gravity, to guide the next flight experiments.
- **Everyone** can check every claim, because each number, ranking and answer links back to its NASA record.

### Tools used

- Data pipeline and AI layer: Python, the PSI public API, an OpenAI-compatible client for Groq
- AI models: GPT-OSS 20B and GPT-OSS 120B (open-weight, served by Groq)
- API: FastAPI with rank-bm25, hosted on Render
- Dashboard: Next.js 16 static export, React, Tailwind CSS, Motion, hand-built SVG charts, hosted on GitHub Pages
- Testing and deploy: Python unittest, Vitest, ESLint, TypeScript, GitHub Actions

### Limits

PSI holds no partial-gravity combustion data yet. Microgravity and 1 g results bound what may happen on the Moon or Mars, and E-FIELD's electric-field flames serve only as a proxy. The Mars habitat atmosphere is not given in the challenge, so that target is labelled as assumed.

## NASA data used

All data comes from NASA's Physical Sciences Informatics (PSI) system, through its public API. No login is needed.

- PSI repository: https://psi.nasa.gov/physci/repo/search?data_source=psi&data_type=investigation
- PSI search API: https://psi.nasa.gov/geode-py/ws/repo/search
- Complete PSI Database Guide: https://assets.science.nasa.gov/content/dam/science/bps/bps-general/bps-data_osdr_psi/Complete_PSI_Database_Guide.pdf

The 24 combustion investigations used:

| Accession | Investigation | Tests in our table |
|---|---|---|
| [PSI-10](https://psi.nasa.gov/physci/repo/data/investigations/PSI-10) | ACME Flame Design | 327 |
| [PSI-20](https://psi.nasa.gov/physci/repo/data/investigations/PSI-20) | ACME Burning Rate Emulator (BRE) | metadata only |
| [PSI-21](https://psi.nasa.gov/physci/repo/data/investigations/PSI-21) | ACME Coflow Laminar Diffusion Flame (CLD Flame) | metadata only |
| [PSI-22](https://psi.nasa.gov/physci/repo/data/investigations/PSI-22) | ACME Electric-Field Effects on Laminar Diffusion Flames (E-FIELD Flames) | metadata only |
| [PSI-23](https://psi.nasa.gov/physci/repo/data/investigations/PSI-23) | ACME Structure and Response of Spherical Diffusion Flames (s-Flame) | metadata only |
| [PSI-25](https://psi.nasa.gov/physci/repo/data/investigations/PSI-25) | Burning and Suppression of Solids II (BASS-II) | 129 |
| [PSI-26](https://psi.nasa.gov/physci/repo/data/investigations/PSI-26) | Burning and Suppression of Solids (BASS) | 121 |
| [PSI-39](https://psi.nasa.gov/physci/repo/data/investigations/PSI-39) | Cool Flames Investigation (CFI) | 79 |
| [PSI-47](https://psi.nasa.gov/physci/repo/data/investigations/PSI-47) | Dust and Aerosol Measurement Feasibility Test (DAFT and DAFT-2) | metadata only |
| [PSI-60](https://psi.nasa.gov/physci/repo/data/investigations/PSI-60) | Computational and Experimental Analysis of SPICE Data Sets | metadata only |
| [PSI-62](https://psi.nasa.gov/physci/repo/data/investigations/PSI-62) | Concurrent Flame Spread Modeling Compared with BASS | metadata only |
| [PSI-68](https://psi.nasa.gov/physci/repo/data/investigations/PSI-68) | Flame Extinguishment Experiment 2 (FLEX-2) | metadata only |
| [PSI-69](https://psi.nasa.gov/physci/repo/data/investigations/PSI-69) | Flame Extinguishment Experiment (FLEX) | 274 |
| [PSI-98](https://psi.nasa.gov/physci/repo/data/investigations/PSI-98) | Spacecraft Fire Safety Experiment I (SAFFIRE-I) | 2 |
| [PSI-99](https://psi.nasa.gov/physci/repo/data/investigations/PSI-99) | Spacecraft Fire Experiment II (SAFFIRE-II) | 9 |
| [PSI-100](https://psi.nasa.gov/physci/repo/data/investigations/PSI-100) | Spacecraft Fire Experiment III (SAFFIRE-III) | 2 |
| [PSI-101](https://psi.nasa.gov/physci/repo/data/investigations/PSI-101) | Smoke Aerosol Measurement Experiment Reflight (SAME-R) | 109 |
| [PSI-102](https://psi.nasa.gov/physci/repo/data/investigations/PSI-102) | Smoke and Aerosol Measurement Experiment (SAME) | 20 |
| [PSI-106](https://psi.nasa.gov/physci/repo/data/investigations/PSI-106) | Structure and Liftoff In Combustion Experiment (SLICE) | metadata only |
| [PSI-107](https://psi.nasa.gov/physci/repo/data/investigations/PSI-107) | Smoke Point In Co-flow Experiment (SPICE) | 435 |
| [PSI-115](https://psi.nasa.gov/physci/repo/data/investigations/PSI-115) | Using SAME Data for Modeling Smoke Generation in Microgravity | metadata only |
| [PSI-117](https://psi.nasa.gov/physci/repo/data/investigations/PSI-117) | Thermo-Convective Perturbation and Cool Flame Dynamics (CFD analysis) | metadata only |
| [PSI-142](https://psi.nasa.gov/physci/repo/data/investigations/PSI-142) | Cool Flame Transitions at Radiation and Stretch Extinction | metadata only |
| [PSI-159](https://psi.nasa.gov/physci/repo/data/investigations/PSI-159) | ACME Cool Flames Investigation with Gases (CFI-G) | 333 |

"Metadata only" means PSI has no experimental table we could normalize for it, so it is ranked on its text, publications and files.

## References and other sources

- NASA Space Apps Challenge 2026, Flame in Freefall: https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/
- Habitat oxygen and pressure targets are quoted from the challenge text. Each one, with any assumption we made, is listed on the dashboard's Method page.
- Publications for each investigation are listed on its page in the dashboard and in `data/processed/investigations.json`, as given by PSI.
- Groq API: https://console.groq.com
- rank-bm25: https://github.com/dorianbrown/rank_bm25

Data courtesy of NASA's Physical Sciences Informatics system. This project is not endorsed by NASA.

## Use of AI

- **GPT-OSS 20B** (open-weight, via Groq) drafted the plain-language summary of each investigation and extracted fuels, sample geometry, sensors and suggested fire-safety pillars from NASA's text. Facts the tables prove were given to it as ground truth, and anything not in the source is flagged. A team member hand-checks the pillar tags, and the hand-checked tags take priority over the model's.
- **GPT-OSS 120B and 20B** (open-weight, via Groq) wrote the two-sentence ranking reasons and the three insight briefs from facts computed by code. Code checks every number, rank and citation, and replaces failures with a labelled fact-only template.
- **GPT-OSS 20B, with 120B as fallback**, answers questions on the Ask page, only from retrieved NASA passages and with required citations.
- **Claude Code** (Anthropic) was the coding assistant for the whole team. It helped write and review the software, and team members reviewed and tested all of it.
- **No AI** is used in the ranking scores, the unit conversions or the charts. Those are deterministic code with tests.

## Open for T5

- Confirm the 2026 field names and length limits, and trim the short summary if needed.
- Check that the challenge link opens. It could not be loaded from the laptop that drafted this.
- Add the demo video link once it is uploaded. The script is in `video-script.md`.
