"""Cited question answering for /ask (task A4).

BM25 search over passages built from the data: each investigation's objective, approach, hypothesis, S2 summary,
publication titles and a plain-text digest of its tests.csv rows, plus the SAFFIRE-II gravity comparison and one
cross-investigation overview. The top 5 go to the LLM, which must answer only from them and cite accession numbers.
An answer without a valid citation gets one retry, then becomes "Not covered in PSI data."
An answer that says an investigation varied oxygen, when its test table shows one oxygen level, gets one retry with the
problem named, and any sentence still making that claim is dropped. The same goes for an oxygen range given for one named
investigation that falls outside its table.
"""

import re
from collections import Counter, defaultdict
from typing import Callable, Dict, List, Optional, Tuple

from rank_bm25 import BM25Okapi

NOT_COVERED = "Not covered in PSI data."
TOP_K = 5
MAX_CHUNK_CHARS = 1500
MAX_TABLE_CHUNK_CHARS = 3000
MAX_TABLE_GROUPS = 8
GRAVITY_ACCESSION = "PSI-99"
OVERVIEW = "OVERVIEW"

DASHES = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212-"
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
Do not judge which option is better, safer or more effective unless a source says so in words. Report what was observed,
for example the lowest oxygen at which a flame went out, and note that this alone does not rank the options.
Give each fact only to the investigation whose source states it. Never merge investigations with similar names, such as
BASS and BASS-II or SAME and SAME-R, into one claim.
A count of zero in a source is an answer. If the overview says 0 rows meet a condition, say that no PSI test met it,
give the highest value it reports instead, and cite the investigations it names for that value.
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
            per_investigation = defaultdict(list)
            for row in measured:
                per_investigation[_label(row)].append(row["o2_mole_fraction"])
            ranges = "; ".join(f"{label} {_pct_range(values)}" for label, values in sorted(per_investigation.items()))
            line += (f" {len(measured)} have measured oxygen: {ranges}."
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


BASIS_WORDS = {"measured": "measured", "planned": "planned", "nominal_cabin_air": "assumed cabin air",
               "test_day_list": "per test day", "approximate": "approximate"}


def _span(low_high: List[float], scale: float, percent: bool) -> str:
    low, high = low_high[0] * scale, low_high[1] * scale
    mark, unit = ("%", " O2") if percent else ("", " kPa")
    return f"{low:.0f}{mark}{unit}" if round(low) == round(high) else f"{low:.0f}{mark} to {high:.0f}{mark}{unit}"


def variation_summary(investigations: List[dict]) -> str:
    """Complete lists, from the test tables, of which investigations varied oxygen or pressure and which ran at one level."""
    oxygen, pressure, single = [], [], []
    for item in sorted(investigations, key=lambda i: int(i["accession"].split("-")[1])):
        label = f"{item.get('acronym') or item['accession']} ({item['accession']})"
        varied = item.get("variables_varied") or []
        o2 = item.get("o2_range")
        basis = BASIS_WORDS.get(item.get("o2_basis"), item.get("o2_basis") or "")
        if "oxygen concentration" in varied and o2:
            oxygen.append(f"{label} {_span(o2, 100, True)}" + (f" ({basis})" if basis else ""))
        elif o2 and o2[1] - o2[0] < 0.01:
            single.append(f"{label} about {o2[0] * 100:.0f}% O2" + (f" ({basis})" if basis else ""))
        if "pressure" in varied and item.get("pressure_kpa_range"):
            pressure.append(f"{label} {_span(item['pressure_kpa_range'], 1, False)}")
    lines = [f"Varied-oxygen: the test tables vary oxygen concentration in {len(oxygen)} investigations: {'; '.join(oxygen)}."]
    if pressure:
        lines.append(f"Varied-pressure: the test tables vary pressure in {len(pressure)} investigations: {'; '.join(pressure)}.")
    if single:
        lines.append(f"Single-oxygen: these ran at one oxygen level and did not vary it: {'; '.join(single)}.")
    return "\n".join(lines)


def build_chunks(investigations: List[dict], raw: Dict[str, dict], extracted: Optional[Dict[str, dict]] = None,
                 tests: Optional[List[dict]] = None, gravity: Optional[List[dict]] = None) -> List[dict]:
    """Searchable passages. The summary comes from investigations.json once D5 merges it, else from extracted.json (S2)."""
    rows_by_accession = defaultdict(list)
    for row in tests or []:
        rows_by_accession[row["accession"]].append(row)
    chunks = []
    if tests:
        text = overview_summary(tests) + "\n" + variation_summary(investigations)
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


ANY_DASH = re.compile("[" + DASHES + "]")


WORD_ACRONYMS = {"same", "flex", "spice", "slice", "bass"}


def _mentions(text: str, name: str) -> bool:
    text = ANY_DASH.sub("-", text)
    flags = 0 if ANY_DASH.sub("-", name).lower() in WORD_ACRONYMS else re.I
    for variant in {name, name.replace("/", " ")}:
        variant = ANY_DASH.sub("-", variant)
        if re.search(r"(?<![\w-])" + re.escape(variant) + r"(?![\w-])", text, flags):
            return True
    return False


def expand_overview(text: str, sources: List[dict], acronyms: Optional[Dict[str, str]] = None) -> str:
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
    mentioned = [a for a in accessions if (acronyms or {}).get(a) and _mentions(text, acronyms[a])]
    accessions = mentioned or accessions
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


OXYGEN_WORD = re.compile(r"\b(oxygen|o2|o\u2082)\b", re.I)
VARIED_CLAIM = re.compile(
    r"\b(?:vary|varies|varied|varying|changed|changing)\b(?:\W+\w+){0,3}?\W+(?:oxygen|o2|o\u2082)\b"
    r"|\b(?:oxygen|o2|o\u2082)\b(?:\W+\w+){0,3}?\W+(?:was|were|is|are)\W+(?:varied|changed)\b"
    r"|\b(?:different|several|multiple|various|range of)\W+(?:oxygen|o2|o\u2082)\W+(?:levels?|concentrations?|fractions?)\b",
    re.I)
CONTRAST_WORD = re.compile(r"cabin air|assumed|did not vary|didn't vary|not varied|without varying|one oxygen|single oxygen|"
                           r"oxygen(?: \w+){0,3} (?:constant|fixed|unchanged)|(?:constant|fixed) oxygen", re.I)
NUMBER = r"(\d+(?:\.\d+)?)"
JOIN = r"\s?%?\s?(?:to|and|[" + DASHES + r"])\s?"
OXYGEN_RANGE = re.compile(NUMBER + JOIN + NUMBER + r"\s?%\s?(?:O2|O\u2082|oxygen)\b"
                          r"|\b(?:oxygen|O2|O\u2082)\b(?:\W+\w+){0,4}?\W+" + NUMBER + JOIN + NUMBER + r"\s?%", re.I)
CITED_ACCESSION = re.compile(r"PSI-\d+")
TARGET_WORD = re.compile(r"\b(lunar|moon|mars|martian|band|target|spacesuit)\b", re.I)
RANGE_TOLERANCE = 1.0

OXYGEN_RETRY = """

Your previous answer was:
{answer}

Its oxygen claims disagree with the test tables:
{problems}
Rewrite the answer with the same facts, giving each investigation only its own oxygen values. Keep the citations."""


def oxygen_facts(investigations: List[dict]) -> Dict[str, Tuple[str, float, float, bool]]:
    """Accession to (acronym, lowest O2, highest O2, ran at one level) from each investigation's test table."""
    facts = {}
    for item in investigations:
        low_high = item.get("o2_range")
        if not low_high or not item.get("acronym"):
            continue
        varied = "oxygen concentration" in (item.get("variables_varied") or [])
        facts[item["accession"]] = (item["acronym"], low_high[0], low_high[1], not varied and low_high[1] - low_high[0] < 0.01)
    return facts


def _sentences(text: str) -> List[str]:
    return [part for part in re.split(r"(?<=[.!?])\s+|\n+", text) if part.strip()]


def _oxygen_ranges(sentence: str) -> List[Tuple[float, float]]:
    found = []
    for groups in OXYGEN_RANGE.findall(sentence):
        values = [float(g) for g in groups if g]
        if len(values) == 2:
            found.append((values[0], values[1]))
    return found


def _sentence_problems(sentence: str, facts: Dict[str, Tuple[str, float, float, bool]]) -> List[str]:
    if not OXYGEN_WORD.search(sentence):
        return []
    named = [(accession, fact) for accession, fact in facts.items() if _mentions(sentence, fact[0])]
    if not named:
        cited = list(dict.fromkeys(a for a in CITED_ACCESSION.findall(sentence) if a in facts))
        if len(cited) == 1:
            named = [(cited[0], facts[cited[0]])]
    problems = []
    if VARIED_CLAIM.search(sentence) and not CONTRAST_WORD.search(sentence):
        for accession, (acronym, low, _, single) in named:
            if single:
                problems.append(f"{accession} {acronym} ran at one oxygen level, about {low * 100:.1f}%")
    if len(named) == 1 and not TARGET_WORD.search(sentence):
        accession, (acronym, low, high, _) = named[0]
        for start, end in _oxygen_ranges(sentence):
            if start < low * 100 - RANGE_TOLERANCE or end > high * 100 + RANGE_TOLERANCE:
                problems.append(f"{accession} {acronym} ran from {low * 100:.1f}% to {high * 100:.1f}% oxygen, not {start:g}% to {end:g}%")
                break
    return problems


def oxygen_problems(text: str, facts: Dict[str, Tuple[str, float, float, bool]]) -> List[str]:
    problems = []
    for sentence in _sentences(text):
        problems.extend(p for p in _sentence_problems(sentence, facts) if p not in problems)
    return problems


def drop_oxygen_claims(text: str, facts: Dict[str, Tuple[str, float, float, bool]]) -> str:
    lines = []
    for line in text.split("\n"):
        kept = [part for part in re.split(r"(?<=[.!?])\s+", line) if part.strip() and not _sentence_problems(part, facts)]
        if kept or not line.strip():
            lines.append(" ".join(kept))
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def answer(question: str, retriever: Retriever, chat: Optional[Callable[[str, str], str]],
           oxygen_levels: Optional[Dict[str, Tuple[str, float, float, bool]]] = None) -> dict:
    """chat(system, prompt) returns the model's text. None means no LLM is configured."""
    sources = retriever.search(question)
    if not sources:
        return {"answer": NOT_COVERED, "covered": False, "citations": [], "sources": []}
    if chat is None:
        raise ChatUnavailable("no LLM_API_KEY is configured on the server")
    prompt = build_prompt(question, sources)
    allowed = {s["accession"] for s in sources} | {a for s in sources for a in re.findall(r"PSI-\d+", s["text"])}
    acronyms = {c["accession"]: c["acronym"] for c in retriever.chunks if c["accession"] != OVERVIEW}
    text = expand_overview(normalize_citations(chat(SYSTEM_PROMPT, prompt).strip()), sources, acronyms)
    if not _refused(text) and not _valid_citations(text, allowed):
        retry = prompt + CITE_RETRY.format(answer=text, overview=OVERVIEW)
        text = expand_overview(normalize_citations(chat(SYSTEM_PROMPT, retry).strip()), sources, acronyms)
    if oxygen_levels and not _refused(text):
        problems = oxygen_problems(text, oxygen_levels)
        if problems:
            retry = prompt + OXYGEN_RETRY.format(answer=text, problems="\n".join(problems))
            text = expand_overview(normalize_citations(chat(SYSTEM_PROMPT, retry).strip()), sources, acronyms)
            if oxygen_problems(text, oxygen_levels):
                text = drop_oxygen_claims(text, oxygen_levels)
    cited = _valid_citations(text, allowed)
    covered = not _refused(text) and bool(cited)
    if not covered:
        text = NOT_COVERED
        cited = []
    return {"answer": text, "covered": covered, "citations": cited, "sources": sources}
