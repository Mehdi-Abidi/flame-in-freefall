"""Flame in Freefall API (tasks A1 to A5).

Run locally:
    uvicorn api.main:app --reload
Then open http://127.0.0.1:8000/docs
"""

import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel, Field

from api import ask as ask_module
from api import guide as guide_module
from api.data import Store, parse_accessions
from api.limits import RateLimiter, visitor_key
from si import rank as si_rank
from si.llm import LLM, LLMError

COMPARE_FIELDS = (
    "acronym", "title", "project_type", "platform", "hardware", "pillars", "fuel_phase",
    "variables_varied", "variables_fixed", "sensors", "o2_range", "o2_basis",
    "pressure_kpa_range", "pressure_basis", "n_tests", "n_records", "n_experimental_tables", "n_files",
)

store = Store()
ask_limiter = RateLimiter.from_env()
retriever = ask_module.Retriever(ask_module.build_chunks(store.investigations, store.raw, store.extracted, store.tests, store.gravity))
oxygen_levels = ask_module.oxygen_facts(store.investigations)
_llm = None

try:
    rank_inputs, rank_load_error = si_rank.load_inputs(), None
except si_rank.RankError as error:
    rank_inputs, rank_load_error = None, str(error)


ASK_MODEL_TIMEOUT = 35


def llm_chat():
    """Returns chat(system, prompt) backed by si/llm.py, or None when no LLM_API_KEY is set."""
    global _llm
    if _llm is None:
        try:
            _llm = LLM(max_retries=0, timeout=ASK_MODEL_TIMEOUT)
        except LLMError:
            return None
    return lambda system, prompt: _llm.chat(prompt, system=system, max_tokens=800)


app = FastAPI(
    title="Flame in Freefall API",
    description="NASA PSI microgravity combustion investigations, tests, habitat rankings and cited Q&A.",
    version="0.1.0",
)

DEFAULT_ORIGINS = "https://mehdi-abidi.github.io,http://localhost:3000"


def cors_origins(value: Optional[str]) -> List[str]:
    """Allowed browser origins. Unset or empty falls back to the dashboard and local dev, never to every site."""
    origins = [origin.strip() for origin in (value or "").split(",") if origin.strip()]
    return origins or DEFAULT_ORIGINS.split(",")


app.add_middleware(CORSMiddleware, allow_origins=cors_origins(os.environ.get("CORS_ORIGINS")),
                   allow_methods=["GET", "POST"], allow_headers=["*"])


def _not_found(accession: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Unknown investigation {accession!r}. See /investigations.")


@app.get("/", include_in_schema=False)
def root():
    """The bare API link opens the interactive docs instead of a 404."""
    return RedirectResponse(url="/docs")


@app.get("/health")
def health():
    return {"status": "ok", "investigations": len(store.investigations), "tests": len(store.tests)}


@app.get("/investigations")
def list_investigations():
    return store.investigations


@app.get("/investigations/{accession}")
def get_investigation(accession: str):
    item = store.investigation(accession)
    if item is None:
        raise _not_found(accession)
    return item


RECORD_TYPES = {"test", "test_day", "test_day_condition", "condition_matrix", "session"}


def _filtered_tests(accession, o2_min, o2_max, p_min, p_max, measured_only, record_type):
    if record_type is not None:
        record_type = record_type.strip().lower()
        if record_type not in RECORD_TYPES:
            raise HTTPException(status_code=422, detail=f"record_type must be one of: {', '.join(sorted(RECORD_TYPES))}")
    accessions = parse_accessions(accession)
    unknown = [a for a in accessions if a not in store.by_accession]
    if unknown:
        raise _not_found(unknown[0])
    return store.filter_tests(accessions or None, o2_min, o2_max, p_min, p_max, measured_only, record_type)


@app.get("/tests")
def list_tests(
    accession: Optional[str] = Query(None, description="One or more accessions, comma separated, e.g. PSI-69,PSI-68"),
    o2_min: Optional[float] = Query(None, ge=0, le=1, description="Minimum O2 mole fraction"),
    o2_max: Optional[float] = Query(None, ge=0, le=1, description="Maximum O2 mole fraction"),
    p_min: Optional[float] = Query(None, ge=0, description="Minimum pressure in kPa"),
    p_max: Optional[float] = Query(None, ge=0, description="Maximum pressure in kPa"),
    measured_only: bool = Query(False, description="Only rows whose O2 was measured, not nominal or planned"),
    record_type: Optional[str] = Query(None, description="test, test_day, test_day_condition, condition_matrix, session"),
):
    return _filtered_tests(accession, o2_min, o2_max, p_min, p_max, measured_only, record_type)


@app.get("/export")
def export_tests(
    accession: Optional[str] = Query(None, description="One or more accessions, comma separated. Empty means all."),
    o2_min: Optional[float] = Query(None, ge=0, le=1),
    o2_max: Optional[float] = Query(None, ge=0, le=1),
    p_min: Optional[float] = Query(None, ge=0),
    p_max: Optional[float] = Query(None, ge=0),
    measured_only: bool = False,
    record_type: Optional[str] = None,
):
    rows = _filtered_tests(accession, o2_min, o2_max, p_min, p_max, measured_only, record_type)
    name = "-".join(parse_accessions(accession)) or "all"
    return Response(
        content=store.to_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="flame-in-freefall-tests-{name}.csv"'},
    )


def _rank_inputs():
    if rank_inputs is None:
        raise HTTPException(status_code=500, detail=f"Ranking data could not be loaded: {rank_load_error}")
    return rank_inputs


@app.get("/scenarios")
def list_scenarios():
    """Habitat targets from data/domain/scenarios.json, as validated by si/rank.py."""
    inputs = _rank_inputs()
    return {"tolerance": inputs["scenarios"]["tolerance"], "scenarios": list(inputs["scenarios"]["scenarios"].values())}


@app.get("/rank")
def rank(
    scenario: str = Query("lunar_base", description="iss, lunar_base, pressurized_rover, mars_habitat, spacesuit"),
    w_prevent: float = Query(1.0, description="Prevention slider weight, 0 or more"),
    w_detect: float = Query(1.0, description="Detection slider weight, 0 or more"),
    w_suppress: float = Query(1.0, description="Suppression slider weight, 0 or more"),
    limit: Optional[int] = Query(None, ge=1, le=50),
):
    """Scores from si.rank.rank(). Bad scenario or weights give 400 (UsageError), data problems give 500 (RankError)."""
    inputs = _rank_inputs()
    try:
        weights = si_rank.parse_weights({"prevention": w_prevent, "detection": w_detect, "suppression": w_suppress})
        results = si_rank.rank(scenario, weights, inputs)
    except si_rank.UsageError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except si_rank.RankError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
    return {
        "scenario": inputs["scenarios"]["scenarios"][scenario],
        "weights": weights,
        "component_weights": si_rank.COMPONENT_WEIGHTS,
        "results": results[:limit] if limit else results,
    }


@app.get("/compare")
def compare(ids: str = Query(..., description="2 to 4 accessions, comma separated, e.g. PSI-69,PSI-68")):
    accessions: List[str] = list(dict.fromkeys(parse_accessions(ids)))
    if not 2 <= len(accessions) <= 4:
        raise HTTPException(status_code=422, detail="Pass 2 to 4 distinct accessions in ids.")
    items = []
    for accession in accessions:
        item = store.investigation(accession)
        if item is None:
            raise _not_found(accession)
        items.append(item)
    rows = []
    for field in COMPARE_FIELDS:
        values = [item.get(field) for item in items]
        rows.append({"field": field, "values": values, "differs": any(v != values[0] for v in values[1:])})
    publication_counts = [len(item.get("publications") or []) for item in items]
    rows.append({"field": "n_publications", "values": publication_counts,
                 "differs": len(set(publication_counts)) > 1})
    return {"ids": accessions, "rows": rows, "investigations": items}


def _spend_one_question(http_request: Request) -> None:
    """Counts one question against the visitor and overall limits, or answers 429 with Retry-After."""
    visitor = visitor_key(http_request.headers.get("x-forwarded-for"), http_request.client.host if http_request.client else None)
    allowed, retry_after, scope = ask_limiter.check(visitor)
    if not allowed:
        who = "from you" if scope == "visitor" else "from everyone right now"
        raise HTTPException(status_code=429, detail=f"Too many questions {who}. Try again in {retry_after} s.",
                            headers={"Retry-After": str(retry_after)})


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500,
                          examples=["Which diluent put out droplet flames at lower oxygen, CO2 or helium?"])


@app.post("/ask")
def ask(request: AskRequest, http_request: Request):
    """Answers only from PSI metadata and test data, citing accession numbers. Otherwise 'Not covered in PSI data.'
    Rate limited per visitor and overall; over the limit answers 429 with Retry-After."""
    _spend_one_question(http_request)
    try:
        chat = llm_chat()
        calls = []

        def counted(system, prompt):
            calls.append(1)
            return chat(system, prompt)

        result = ask_module.answer(request.question, retriever, counted if chat else None, oxygen_levels)
        ask_limiter.charge_global(len(calls) - 1)
        return result
    except (ask_module.ChatUnavailable, LLMError) as error:
        raise HTTPException(status_code=503, detail=f"Chat is unavailable right now: {error}") from error


class GuideRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500, examples=["What does Never flown mean?"])
    page: str = Field("", max_length=80, description="The page the visitor is on, for example Cabin lab")
    screen: str = Field("", max_length=2000, description="What that page is showing right now, as plain text")


@app.post("/guide")
def guide(request: GuideRequest, http_request: Request):
    """Wisp, the conversational guide. It may use the dashboard's own description, the visitor's screen and retrieved
    PSI passages, and cites only passages it was given. Shares the /ask rate limits."""
    _spend_one_question(http_request)
    try:
        return guide_module.reply(request.question, request.page, request.screen, retriever, llm_chat(), oxygen_levels)
    except (ask_module.ChatUnavailable, LLMError) as error:
        raise HTTPException(status_code=503, detail=f"Chat is unavailable right now: {error}") from error
