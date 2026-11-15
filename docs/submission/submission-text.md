# Submission text

Text for the Space Apps 2026 project page. The headings below are the form's own field names, in the form's order, from the [2026 Project Submission Guide](https://www.spaceappschallenge.org/resources/project-submission-guide/) (checked 15 November). Facts come from the README, the Method page and `data/processed/`.

## Project Name

Flame in Freefall: fire safety answers from NASA's microgravity combustion data

## High-Level Project Summary

Lunar habitats are expected to run at 30% oxygen or more, yet no solid-material fire test in NASA's Physical Sciences Informatics (PSI) repository ran above 22.2%. Flame in Freefall turns PSI's 24 combustion investigations into a fire safety dashboard. You pick a habitat (ISS, lunar base, pressurized rover, Mars habitat or spacesuit) and see which experiments matter for it, which conditions were actually tested and where the data runs out. You can also ask questions in plain English and get answers that cite NASA's records. Flammability rises steeply with oxygen, so knowing what has never been tested matters before crews live on the Moon.

## Link to Project Demo

- 30-second video: add the link once it is uploaded. It must open in a private window with no sign-in.

## Link to Final Project

- Live dashboard: https://mehdi-abidi.github.io/flame-in-freefall/

The form takes one link. Put these two in the detailed description:

- Source code: https://github.com/Mehdi-Abidi/flame-in-freefall
- Public API: https://flame-in-freefall-api.onrender.com (docs at `/docs`)

## Detailed Project Description

### What it does

NASA has flown dozens of fire experiments on the International Space Station. Their results sit in PSI as 24 investigations, 21 experimental tables and more than 82,000 raw files. That is hard to search when you are designing a habitat and need to know how a fabric burns at 30% oxygen. The dashboard answers that in eight views, with a guide on every page:

- **Mission brief** is the home page, told as one scroll: the headline gap, a scroll scene where NASA's candle flame loses gravity and turns from a teardrop into a blue dome, the 22.2% versus 30% gap, live verdicts for three cabins, and the five-step data pipeline with the number each step produced.
- **Evidence** holds the detail. An oxygen ruler compares the oxygen measured for each fuel phase with the lunar band. A gap map plots every test by oxygen and pressure against the habitat boxes. A SAFFIRE-II panel compares the same materials burned in microgravity and at 1 g. Three reviewed briefs, one per pillar, sit beside a FLEX comparison of how droplet flames went out by diluent. A "What to fly next" section proposes four experiments, each with its evidence from the tables.
- **Cabin lab** lets you set the oxygen, pressure, fuel and gravity of a cabin of your own. It counts the flight tests NASA ran near that cabin, shows how they ended and how far the cabin sits past the record, and lists the closest tests. The flame on screen is drawn solid only where tests exist. Nothing in it is a prediction.
- **Orb, the guide** sits on every page. Name a habitat and it answers at once with a card counted from the flight tests. Ask what a page does and it explains it. Any other question goes to the same cited question service as the Ask page. You can type or speak, and it can read its answers aloud.
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
- **Fire modelers** get one clean test table in common units, filterable by oxygen, pressure and investigation, and downloadable as CSV from the home page, the Evidence page, each investigation's page or the API.
- **Researchers and planners** see where data is missing, such as solids above 22% oxygen and partial gravity, to guide the next flight experiments.
- **Everyone** can check every claim, because each number, ranking and answer links back to its NASA record.

### What we hope to achieve

We want a habitat designer to learn in a minute what took us two days of reading: which fire questions NASA's orbital data can answer for the Moon, and which it cannot yet. The four recommended experiments are our handover to the teams planning the next flights. NASA expects partial-gravity results from the Lunar-g Combustion Investigation (LUCI) and Flammability of Materials on the Moon (FM2) to reach PSI. When they do, the same pipeline can place them on the map, and the gap will start to close.

### Tools used

- Data pipeline and AI layer: Python, the PSI public API, an OpenAI-compatible client for Groq
- AI models: GPT-OSS 20B and GPT-OSS 120B (open-weight, served by Groq)
- API: FastAPI with rank-bm25, hosted on Render
- Dashboard: Next.js 16 static export, React, Tailwind CSS, Motion, hand-built SVG charts, hosted on GitHub Pages
- Testing and deploy: Python unittest, Vitest, ESLint, TypeScript, GitHub Actions

### Limits

PSI holds no partial-gravity combustion data yet. Microgravity and 1 g results bound what may happen on the Moon or Mars, and E-FIELD's electric-field flames serve only as a proxy. The Mars habitat atmosphere is not given in the challenge, so that target is labelled as assumed.

## NASA Data

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

## Space Agency Partner Data and Other References

We used no Space Agency Partner data. PSI's combustion records are NASA's.

- NASA Space Apps Challenge 2026, Flame in Freefall: https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/
- Habitat oxygen and pressure targets are quoted from the challenge text. Each one, with any assumption we made, is listed on the dashboard's Method page.
- Publications for each investigation are listed on its page in the dashboard and in `data/processed/investigations.json`, as given by PSI.
- Groq API: https://console.groq.com
- rank-bm25: https://github.com/dorianbrown/rank_bm25
- Open-source code the project is built with: Next.js, React, Tailwind CSS, Motion, Radix UI, d3-scale and d3-delaunay for the dashboard, FastAPI, Uvicorn, pandas and python-dotenv for the API and pipeline
- Type: Barlow Condensed, Host Grotesk and JetBrains Mono (SIL Open Font License)
- The architecture diagram was drawn by the team in Excalidraw. The site uses no NASA logos.
- Photographs, all from the NASA Image and Video Library (https://images.nasa.gov): a candle flame in normal gravity and in microgravity (GRC-1998-C-00485, cropped to the two flames), Earthset from Orion on Artemis II (art002e021278), Earthrise from Apollo 8 (AS08-14-2383), and fabric and plexiglass burning in Saffire-IV (jsc2023e046375, jsc2023e046631).

Data courtesy of NASA's Physical Sciences Informatics system. This project is not endorsed by NASA.

## Use of Super Intelligence (SI)

- **GPT-OSS 20B** (open-weight, via Groq) drafted the plain-language summary of each investigation and extracted fuels, sample geometry, sensors and suggested fire-safety pillars from NASA's text. Facts the tables prove were given to it as ground truth, and anything not in the source is flagged. A team member hand-checks the pillar tags, and the hand-checked tags take priority over the model's.
- **GPT-OSS 120B and 20B** (open-weight, via Groq) wrote the two-sentence ranking reasons from facts computed by code. Code checks every number, rank and citation, and replaces failures with a labelled fact-only template.
- **Claude** (Anthropic) drafted the three insight briefs from facts computed by code. They passed the same automatic checks and were reviewed by a team member, and the site labels them that way.
- **GPT-OSS 20B, with 120B as fallback**, answers questions on the Ask page and for Orb, the guide, only from retrieved NASA passages and with required citations. Orb's habitat cards, page help and record counts come from code, not from a model.
- **Claude Code** (Anthropic) was the coding assistant for the whole team. It helped write and review the software, and team members reviewed and tested all of it.
- **No SI** is used in the ranking scores, the unit conversions or the charts. Those are deterministic code with tests.
- **No SI-generated images, video or recorded audio** are in the project. The ambient sound, which plays after a visitor's first click and can be muted, is synthesized live in the browser by code, with no sample or recording. The flame in the cabin lab and the guide's character are drawn in code, and the flame is labelled as an illustration. Spoken questions and read-aloud answers use the visitor's own browser speech features, with no recorded or generated voice files. The demo is a screen recording of the live site with a team member's voice.
- **How it is marked.** The ranking reasons and briefs carry their source and model name in the data files, and the dashboard prints a label under every model-written text. Fact-only templates are labelled as such.

## Before pressing Submit for Judging

- Add the demo link, then open it and the dashboard in a private window.
- The video must be 30 seconds or less. A longer one is not eligible for Global Judging.
- The deadline is Sunday 15 November, 23:59 local time. Only the last saved submission is judged.
- Tick both boxes: the terms and conditions, and that all work is original.
- Optional, and the guide recommends it for new sites: ask FortiGuard to classify the dashboard address so judges' networks do not block it.
