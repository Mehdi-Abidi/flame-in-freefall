"""Cited question answering for /ask (task A4).

BM25 search over passages built from the data: each investigation's objective, approach, hypothesis, S2 summary,
publication titles and a plain-text digest of its tests.csv rows, plus the SAFFIRE-II gravity comparison and one
cross-investigation overview. The top 5 go to the LLM, which must answer only from them and cite accession numbers.
An answer without a valid citation gets one retry, then becomes "Not covered in PSI data."
"""

import re
from collections import Counter, defaultdict
from typing import Callable, Dict, List, Optional

from rank_bm25 import BM25Okapi

NOT_COVERED = "Not covered in PSI data."
TOP_K = 5
MAX_CHUNK_CHARS = 1500
MAX_TABLE_CHUNK_CHARS = 3000
MAX_TABLE_GROUPS = 8
GRAVITY_ACCESSION = "PSI-99"
OVERVIEW = "OVERVIEW"

DASHES = "‐‑‒–—―−-"
CITATION_VARIANTS = re.compile(r"PSI\s*[" + DASHES + r"]\s*(\d+)")

STOPWORDS = set("""
a an and are as at be by can do does for from has have how in is it its of on or that the this to was were what
when where which who why will with into than then there these those their they our we you your about over under
""".split())

GAS_WORDS = {"N2": "nitrogen", "CO2": "carbon dioxide", "He": "helium"}

SYSTEM_PROMPT = f"""You answer questions about NASA microgravity combustion experiments for spacecraft fire safety.
Use ONLY the sources in the user message. Do not use outside knowledge.
Each source starts with its accession number in square brackets, for example [PSI-69].
Cite every claim with that accession number in square brackets, for example [PSI-69]. Never cite by position.
The [{OVERVIEW}] source covers many investigations: cite the accession numbers named inside it, never [{OVERVIEW}].
Keep the answer under 150 words, in plain language for a habitat designer.
Report numbers as the sources give them. If a difference is small or the data cannot settle the question, say so.
If the sources do not answer the question, reply with exactly: {NOT_COVERED}"""


class ChatUnavailable(RuntimeError):
    pass


def tokenize(text: str) -> List[str]:
    return [word for word in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", (text or "").lower()) if word not in STOPWORDS]


def _describe_gas(diluent: Optional[str]) -> str:
    if not diluent:
        return "diluent not recorded"
    if "air" in diluent.lower():
        return "air"
    words = [GAS_WORDS.get(re.sub(r"[()]", "", part).strip(), "") for part in re.split(r"\+| or |\s", diluent)]
    words = [w for w in dict.fromkeys(words) if w]
    return f"{diluent} ({' and '.join(words)})" if words else diluent


def _pct_range(values: List[float]) -> str:
    low, high = min(values) * 100, max(values) * 100
    return f"{low:.0f}% O2" if round(low) == round(high) else f"{low:.0f}% to {high:.0f}% O2"


def _kpa_range(values: List[float]) -> str:
    low, high = min(values), max(values)
    return f"{low:.0f} kPa" if round(low) == round(high) else f"{low:.0f} to {high:.0f} kPa"


def table_summary(acronym: str, accession: str, rows: List[dict]) -> str:
    """Plain-text digest of one investigation's tests.csv rows, grouped by fuel and diluent."""
    fuels = Counter(row["fuel"] for row in rows if row.get("fuel"))
    lines = [f"Test table summary for {acronym} ({accession}): {len(rows)} rows."]
    if fuels:
        lines.append("Fuels: " + ", ".join(f"{fuel} ({n})" for fuel, n in fuels.most_common(6)) + ".")
    groups = defaultdict(list)
    for row in rows:
        groups[(row.get("fuel") or "fuel not recorded", row.get("diluent"))].append(row)
    ordered = sorted(groups.items(), key=lambda item: -len(item[1]))
    for (fuel, diluent), group in ordered[:MAX_TABLE_GROUPS]:
        parts = [f"{fuel} with {_describe_gas(diluent)}: {len(group)} rows"]
        o2 = [row["o2_mole_fraction"] for row in group if row.get("o2_mole_fraction") is not None]
        if o2:
            bases = sorted({row["o2_source"] for row in group if row.get("o2_source")})
            parts.append(f"{_pct_range(o2)} ({', '.join(bases)})")
        pressure = [row["pressure_kpa"] for row in group if row.get("pressure_kpa") is not None]
        if pressure:
            bases = sorted({row["pressure_source"] for row in group if row.get("pressure_source")})
            parts.append(f"{_kpa_range(pressure)} ({', '.join(bases)})")
        outcomes = defaultdict(list)
        for row in group:
            if row.get("outcome"):
                outcomes[row["outcome"]].append(row.get("o2_mole_fraction"))
        if outcomes:
            described = []
            for outcome, values in sorted(outcomes.items(), key=lambda item: -len(item[1])):
                known = [v for v in values if v is not None]
                described.append(f"{outcome} {len(values)}" + (f" at {_pct_range(known)}" if known else ""))
            parts.append("outcomes: " + "; ".join(described))
        lines.append(", ".join(parts) + ".")
    if len(ordered) > MAX_TABLE_GROUPS:
        lines.append(f"{len(ordered) - MAX_TABLE_GROUPS} smaller fuel and diluent groups not listed.")
    return "\n".join(lines)


def gravity_summary(rows: List[dict]) -> str:
    """SAFFIRE-II samples burned in microgravity and in normal gravity (data/processed/saffire2_gravity.csv)."""
    lines = ["Microgravity versus normal gravity (1 g) flame spread for the same SAFFIRE-II samples.",
             "Each sample is 5 cm x 29 cm (Saffire-II approach), so a 29 cm burn length means the whole sample burned, "
             "and 'Complete' means the same in 1 g. '~ 0' means it barely burned."]
    for row in rows:
        thickness = row.get("thickness") or ""
        thickness = "thickness unclear in the source" if re.fullmatch(r"0\d+ mm", thickness) else f"{thickness} thick"
        lines.append(
            f"Sample {row.get('sample')}: {row.get('material')}, {thickness}, {row.get('flow_direction')} flow. "
            f"Microgravity burn length {row.get('micro_g_burn_length') or 'not given'}, "
            f"spread rate {row.get('micro_g_spread_length') or 'not given'}. "
            f"Normal gravity (1 g) burn length {row.get('one_g_burn_length') or 'not given'}, "
            f"spread rate {row.get('one_g_spread_rate') or 'not given'}.")
    return "\n".join(lines)


O2_SOURCE_WORDS = {
    "nominal_cabin_air": "ran in cabin air, about 21% O2 assumed",
    "planned": "lists planned O2 levels only",
    "approximate": "gives approximate O2 only",
    "test_day_list": "lists O2 per test day, not per test",
}


def _label(row: dict) -> str:
    return f"{row['acronym']} ({row['accession']})"


def _names(rows: List[dict]) -> str:
    return ", ".join(sorted({_label(row) for row in rows}))


def _why_unmeasured(rows: List[dict]) -> str:
    sources = sorted({row["o2_source"] for row in rows if row.get("o2_source")})
    return "; ".join(O2_SOURCE_WORDS.get(source, source) for source in sources) or "O2 not recorded"


def overview_summary(tests: List[dict]) -> str:
    """Cross-investigation facts by fuel phase, so 'was anything ever tested at X' has an answer. Measured O2 only."""
    lines = ["Dataset overview across all PSI combustion investigations, by fuel phase. Only measured oxygen values count."]
    for phase in ("solid", "liquid", "gas"):
        rows = [row for row in tests if row.get("fuel_phase") == phase]
        if not rows:
            continue
        measured = [row for row in rows if row.get("o2_source") == "measured" and row.get("o2_mole_fraction") is not None]
        line = f"{phase.capitalize()} fuels: {len(rows)} rows in {_names(rows)}."
        if measured:
            o2 = [row["o2_mole_fraction"] for row in measured]
            top = [row for row in measured if row["o2_mole_fraction"] == max(o2)]
            high = [row for row in measured if row["o2_mole_fraction"] >= 0.30]
            line += (f" {len(measured)} have measured oxygen, from {_pct_range(o2)}, in {_names(measured)}."
                     f" Highest measured oxygen for a {phase} fuel: {max(o2) * 100:.1f}% O2, in {_names(top)},"
                     f" burning {', '.join(sorted({r['fuel'] for r in top if r.get('fuel')}))}."
                     f" {len(high)} {phase}-fuel rows have measured O2 of 30% or more" + (f", in {_names(high)}." if high else "."))
        measured_labels = {_label(row) for row in measured}
        by_investigation = defaultdict(list)
        for row in rows:
            if _label(row) not in measured_labels:
                by_investigation[_label(row)].append(row)
        if by_investigation:
            reasons = [f"{label} {_why_unmeasured(group)}" for label, group in sorted(by_investigation.items())]
            line += " No measured oxygen in: " + "; ".join(reasons) + "."
        lines.append(line)
    return "\n".join(lines)


def build_chunks(investigations: List[dict], raw: Dict[str, dict], extracted: Optional[Dict[str, dict]] = None,
                 tests: Optional[List[dict]] = None, gravity: Optional[List[dict]] = None) -> List[dict]:
    """Searchable passages. The summary comes from investigations.json once D5 merges it, else from extracted.json (S2)."""
    rows_by_accession = defaultdict(list)
    for row in tests or []:
        rows_by_accession[row["accession"]].append(row)
    chunks = []
    if tests:
        text = overview_summary(tests)
        chunks.append({"accession": OVERVIEW, "acronym": "All investigations", "field": "dataset overview",
                       "text": text, "tokens": tokenize(f"dataset overview all investigations tested {text}")})
    for item in investigations:
        accession = item["accession"]
        acronym = item.get("acronym") or accession
        meta = raw.get(accession, {})
        label = f"{acronym}: {item.get('title') or ''}".strip()
        fields = [
            ("objective", meta.get("objective")),
            ("approach", meta.get("approach")),
            ("hypothesis", meta.get("hypothesis")),
            ("summary", item.get("summary") or (extracted or {}).get(accession, {}).get("summary")),
        ]
        titles = [pub.get("title") for pub in item.get("publications") or [] if pub.get("title")]
        if titles:
            fields.append(("publications", "; ".join(titles)))
        if rows_by_accession.get(accession):
            fields.append(("test table", table_summary(acronym, accession, rows_by_accession[accession])))
        if accession == GRAVITY_ACCESSION and gravity:
            fields.append(("gravity comparison", gravity_summary(gravity)))
        for field, text in fields:
            text = (text or "").strip()
            if text:
                limit = MAX_TABLE_CHUNK_CHARS if field in ("test table", "gravity comparison") else MAX_CHUNK_CHARS
                chunks.append({"accession": accession, "acronym": acronym, "field": field,
                               "text": text[:limit], "tokens": tokenize(f"{label} {text}")})
    return chunks


class Retriever:
    def __init__(self, chunks: List[dict]):
        self.chunks = chunks
        self.bm25 = BM25Okapi([chunk["tokens"] for chunk in chunks])

    def search(self, question: str, k: int = TOP_K) -> List[dict]:
        tokens = tokenize(question)
        if not tokens:
            return []
        scores = self.bm25.get_scores(tokens)
        best = sorted(range(len(scores)), key=lambda i: -scores[i])[:k]
        return [{**{key: self.chunks[i][key] for key in ("accession", "acronym", "field", "text")},
                 "score": round(float(scores[i]), 3)} for i in best if scores[i] > 0]


def build_prompt(question: str, sources: List[dict]) -> str:
    blocks = [f"[{s['accession']}] {s['acronym']}, {s['field']}:\n{s['text']}" for s in sources]
    return "Sources:\n\n" + "\n\n".join(blocks) + f"\n\nQuestion: {question}"


def normalize_citations(text: str) -> str:
    return CITATION_VARIANTS.sub(lambda match: "PSI-" + match.group(1), text)


def expand_overview(text: str, sources: List[dict]) -> str:
    """Replace an [OVERVIEW] citation with the accessions from the overview lines the answer is about.

    The model often cites the overview label itself. Each overview line covers one fuel phase, so an answer that
    talks about solids is cited with the solid-fuel investigations. With no phase named, every line counts.
    """
    pattern = re.compile(r"\[\s*" + OVERVIEW + r"\s*\]", re.I)
    overview = next((s["text"] for s in sources if s["accession"] == OVERVIEW), None)
    if overview is None or not pattern.search(text):
        return text
    phase_lines = {line.split()[0].lower(): line for line in overview.split("\n")[1:] if line.strip()}
    named = [line for phase, line in phase_lines.items() if phase in text.lower()] or list(phase_lines.values())
    accessions = list(dict.fromkeys(a for line in named for a in re.findall(r"PSI-\d+", line)))
    return pattern.sub("[" + ", ".join(accessions) + "]", text) if accessions else text


def _valid_citations(text: str, allowed: set) -> List[str]:
    return [a for a in dict.fromkeys(re.findall(r"PSI-\d+", text)) if a in allowed]


def _refused(text: str) -> bool:
    return NOT_COVERED.lower().rstrip(".") in text.lower()


CITE_RETRY = """

Your previous answer was:
{answer}

It did not cite its sources correctly. Rewrite it with the same facts, citing every claim with accession numbers
in square brackets taken from the sources, for example [PSI-69]. Never cite [{overview}]."""


def answer(question: str, retriever: Retriever, chat: Optional[Callable[[str, str], str]]) -> dict:
    """chat(system, prompt) returns the model's text. None means no LLM is configured."""
    sources = retriever.search(question)
    if not sources:
        return {"answer": NOT_COVERED, "covered": False, "citations": [], "sources": []}
    if chat is None:
        raise ChatUnavailable("no LLM_API_KEY is configured on the server")
    prompt = build_prompt(question, sources)
    allowed = {s["accession"] for s in sources} | {a for s in sources for a in re.findall(r"PSI-\d+", s["text"])}
    text = expand_overview(normalize_citations(chat(SYSTEM_PROMPT, prompt).strip()), sources)
    if not _refused(text) and not _valid_citations(text, allowed):
        retry = prompt + CITE_RETRY.format(answer=text, overview=OVERVIEW)
        text = expand_overview(normalize_citations(chat(SYSTEM_PROMPT, retry).strip()), sources)
    cited = _valid_citations(text, allowed)
    covered = not _refused(text) and bool(cited)
    if not covered:
        text = NOT_COVERED
        cited = []
    return {"answer": text, "covered": covered, "citations": cited, "sources": sources}
