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
| `data/processed/tests.csv` | 2,127 normalized rows, each with a unique `row_id`: fuel, phase, geometry, size, O2 fraction, pressure in kPa, flow, outcome |
| `data/processed/saffire2_gravity.csv` | SAFFIRE-II microgravity vs 1 g burn results, sample by sample |

Every O2 and pressure value carries a source tag (`measured`, `planned`, `nominal_cabin_air` and so on), so assumed cabin values are never mistaken for test conditions. Table-by-table units and cleanup decisions are in [`docs/data-notes.md`](docs/data-notes.md).

### What the data already shows

- **No solid-material fire test in PSI ran above 22.2% oxygen.** That covers 140 tests across BASS-II, SAFFIRE-I and SAFFIRE-II. Lunar habitats are expected to run at 30% or more.
- **Only 66 tests sit at lunar-base conditions** (30% O2 or more at 70 kPa or less), and all of them are gas flames from ACME CFI-G and Flame Design.
- **Gravity flips the ranking of materials.** In SAFFIRE-II, thin silicone sheets burned completely at 1 g but barely burned in microgravity, while cotton-fiberglass fabric spread its full 29 cm length in both.

## Progress

| Task | Owner | Status |
|---|---|---|
| Repo, architecture, execution plan | Mehdi | Done |
| D1 Units and quirks of all 21 tables | Mufeed | Done, see `docs/data-notes.md` |
| D2 `pipeline/normalize.py` and `tests.csv` | Mufeed | Done, Mufeed to review |
| D4 `pipeline/qa.py`, 22 automated data checks | Mufeed | Done, all passing |
| D3 `investigations.json` with ranges | Mufeed | Next |
| S1 `si/llm.py` provider wrapper, 17 unit tests | Mehdi | Done |
| S2 Extraction of all 24 investigations | Mehdi | Next |
| A1 FastAPI skeleton | Moiz | Next |
| F1 to F2 React shell and Vercel deploy | Ali Soban | Next |
| V1 Flammability map prototype | Ahsan | Next, can start on `tests.csv` now |
| T1 to T2 Domain tags and habitat scenarios | Taha | Next |

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
copy .env.example .env
python -m si.llm --check
python pipeline/fetch_psi.py
python pipeline/normalize.py
python pipeline/qa.py
```

Put your own free [Groq](https://console.groq.com/keys) key into `.env` as `LLM_API_KEY` before running `si.llm --check`. Never commit `.env`. The fetch and normalize steps are optional because the data is already committed. The fetch downloads under 1 MB.

### LLM setup

`si/llm.py` talks to any OpenAI-compatible provider. Switching provider or model means editing `.env`, not code.

| Setting | Default | Notes |
|---|---|---|
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | OpenRouter, Cerebras and NVIDIA also work |
| `LLM_MODEL` | `openai/gpt-oss-20b` | Open-weight. Scored best in our extraction test (12 of 12 facts present in the text, 0.6 s) |
| `LLM_FALLBACK_MODEL` | `openai/gpt-oss-120b` | Used automatically if the main model fails |

Replies are cached in `.cache/llm/` so reruns do not spend free-tier quota. Rate limits are retried with backoff.

## Repository layout

```
pipeline/   fetch and normalize scripts
data/       raw PSI metadata and tables, processed outputs, domain tags
si/         LLM client, extraction, ranking, insight briefs
tests/      unit tests (run in CI, no API key needed)
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
