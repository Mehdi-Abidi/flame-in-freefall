# Flame in Freefall

**An SI-powered fire safety dashboard built on NASA's microgravity combustion data.**
NASA Space Apps Challenge 2026 · [Flame in Freefall challenge](https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/)

NASA has flown dozens of fire experiments on the International Space Station. The results sit in the [Physical Sciences Informatics (PSI)](https://psi.nasa.gov/physci/repo/search?data_source=psi&data_type=investigation) repository as 24 combustion investigations, about 2,900 logged tests and more than 82,000 raw files. That is a lot to search through when you are designing a lunar habitat and need to know how a fabric burns at 30% oxygen.

This dashboard reads that data, ranks every investigation for a chosen habitat (ISS, lunar base, pressurized rover, Mars habitat), plots exactly which oxygen and pressure conditions were tested, and answers questions with citations back to PSI.

## Architecture

![Architecture diagram](docs/architecture.svg)

The editable source is [`docs/architecture.excalidraw`](docs/architecture.excalidraw). To change it, open [excalidraw.com](https://excalidraw.com), choose *Open*, and pick that file. Export it as SVG over `docs/architecture.svg` when you are done.

Data flows left to right:

1. **NASA data.** The PSI search API gives metadata for all 24 combustion investigations. Each investigation also has an "experimental table" CSV that lists the conditions of every test. Raw videos and sensor dumps (about 16 TB) stay on NASA's servers and are linked, never downloaded.
2. **Ingest and normalize.** `pipeline/fetch_psi.py` pulls metadata and tables (under 1 MB). `normalize.py` converts mmHg, atm and bar to kPa, percent to mole fraction, and tags fuel phase and outcome.
3. **SI layer.** An LLM extracts structured attributes from each investigation (fuel, sample geometry, variables varied and held fixed, sensors). A transparent scoring formula ranks investigations per habitat, and the LLM writes the explanation. All of this is precomputed and committed.
4. **API.** FastAPI serves investigations, tests, rankings, comparisons, CSV export and a cited Q&A endpoint.
5. **Dashboard.** React with Plotly. Pages: Explorer, Flammability Map, Habitat Ranking, Compare, Ask the SI, Gravity Bounds, Earth Spinoffs.

## What it answers

| Challenge objective | Dashboard feature |
|---|---|
| Find investigations most relevant to spacecraft, stations, lunar and Martian bases, pressurized rovers | Habitat Ranking with adjustable prevention, detection and suppression weights |
| Extract data for predictive modeling of flammability | Unified test matrix (O2, pressure, flow, fuel, outcome) with filtered CSV export |
| Highlight research for next-generation fire safety equipment | Insight briefs per pillar, Earth spinoffs page |
| Summarize objectives, fuels, conditions, variables, sensors | Explorer cards and the Compare view |
| Show similarities and differences between investigations | Compare 2 to 4 investigations side by side, differences highlighted |
| Partial gravity | Gravity Bounds panel: microgravity vs 1 g results (SAFFIRE-II), E-FIELD as a proxy |

## Data

Everything comes from NASA PSI's public API. No login is needed.

| Endpoint | Returns |
|---|---|
| `GET https://psi.nasa.gov/geode-py/ws/repo/search?data_source=psi&data_type=investigation&ffield=Research%20Area&fvalue=combustion%20science` | All 24 combustion investigations |
| `GET https://psi.nasa.gov/geode-py/ws/repo/investigations/PSI-69` | Full metadata for one investigation |
| `GET https://psi.nasa.gov/geode-py/ws/repo/investigations/PSI-69/versions` | File manifest |
| `GET https://psi.nasa.gov/geode-py/ws/studies/PSI-69/download?file=<id>&version=1&redirect=false` | Temporary download link for one file |

Already pulled into this repo:

| Path | Contents |
|---|---|
| `data/raw/catalog.json` | Search results for the 24 investigations |
| `data/raw/investigations/PSI-*.json` | Full metadata per investigation (objectives, approach, hardware, publications) |
| `data/raw/tables/*.csv` | 21 experimental tables, about 2,900 test rows |
| `data/raw/index.json` | Summary per investigation, including raw file counts and sizes on PSI |

A first look at the tables: of roughly 1,050 tests with a recorded oxygen value, only about 88 sit at lunar-base conditions (30% O2 or more, 70 kPa or less), and they are all gas flames. The solid-material tests in BASS-II top out near 22% O2. This is a preliminary count and the data team is confirming it.

## Team

| Member | Role |
|---|---|
| Mehdi Abidi | Team lead, SI layer, integration |
| Syed Mufeed Haider | Data engineering |
| Moiz Ul Haq | Backend API |
| Ali Soban | Frontend |
| Ahsan Ali | Data visualization |
| Syed Taha Zaidi | Domain research, demo and submission |

The full hour-by-hour plan, task board, data contracts and ranking formula are in [`docs/EXECUTION_PLAN.md`](docs/EXECUTION_PLAN.md) and [`docs/Execution_Plan.pdf`](docs/Execution_Plan.pdf).

## Getting started

```bash
git clone https://github.com/Mehdi-Abidi/flame-in-freefall.git
cd flame-in-freefall
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python pipeline/fetch_psi.py
```

The last step is optional because the data is already committed. It downloads under 1 MB.

## Repository layout

```
pipeline/   fetch and normalize scripts
data/       raw PSI metadata and tables, processed outputs, domain tags
si/         LLM extraction, ranking, insight briefs
api/        FastAPI service
web/        React dashboard
docs/       architecture diagram, execution plan
```

## Working rules

- Branch per task: `name/TASKID-short-name`, then a PR into `main`.
- Do not commit raw PSI media or anything over 5 MB.
- API keys live in `.env`, which Git ignores.
- Every claim in the UI links back to a PSI accession or NASA source.

## Sources

- [Flame in Freefall challenge](https://www.spaceappschallenge.org/2026/challenges/flame-in-freefall/)
- [NASA PSI repository](https://psi.nasa.gov/physci/repo/search?data_source=psi&data_type=investigation)
- [Complete PSI Database Guide](https://assets.science.nasa.gov/content/dam/science/bps/bps-general/bps-data_osdr_psi/Complete_PSI_Database_Guide.pdf)

Data courtesy of NASA's Physical Sciences Informatics system. This project is not endorsed by NASA.

## License

MIT
