"""
STR (Section-Township-Range) parser for PLSS legal descriptions.

Handles:
  - Oklahoma / standard PLSS aliquot parts: NE/4 SW/4 Sec 14, T12N, R5W
  - Multiple sections in one description
  - Lot/Block descriptions (graceful pass-through, not PLSS-mappable)
  - Texas Abstract descriptions (graceful pass-through, flagged as non-PLSS)
  - Metes-and-bounds fragments (flagged as non-PLSS)

Returns a ParsedLegalDescription with enough info to place the tract on a
6x6 PLSS grid and shade acreage coverage.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AliquotPart:
    """One quarter-call in an aliquot chain, e.g. 'NE/4' or 'SW/4 NE/4'."""
    quarters: list[str]           # ['NE', 'SW'] means SW/4 of NE/4 (inner-first order)
    lots: list[int] = field(default_factory=list)   # government survey lots
    gross_acres: Optional[float] = None


@dataclass
class ParsedSection:
    """A single section reference extracted from a legal description."""
    section: Optional[int] = None         # 1-36
    township_number: Optional[int] = None
    township_dir: Optional[str] = None    # 'N' or 'S'
    range_number: Optional[int] = None
    range_dir: Optional[str] = None       # 'E' or 'W'
    principal_meridian: Optional[str] = None
    aliquot_parts: list[AliquotPart] = field(default_factory=list)
    gross_acres: Optional[float] = None


@dataclass
class ParsedLegalDescription:
    """Result of parsing one legal-description string."""
    raw: str
    is_plss: bool = False
    description_type: str = "unknown"   # 'plss', 'lot_block', 'texas_abstract', 'metes_bounds', 'unknown'
    sections: list[ParsedSection] = field(default_factory=list)
    # For non-PLSS types
    abstract_number: Optional[str] = None
    survey_name: Optional[str] = None
    lot: Optional[str] = None
    block: Optional[str] = None
    subdivision: Optional[str] = None
    parse_notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

_RE_SEC = re.compile(
    r"\bSec(?:tion|\.?)?\s*(\d{1,2})\b",
    re.IGNORECASE,
)

_RE_TWP = re.compile(
    r"\bT(?:ownship|wp\.?)?\s*(\d{1,3})\s*([NS])\b",
    re.IGNORECASE,
)

_RE_RNG = re.compile(
    r"\bR(?:ange|ge\.?)?\s*(\d{1,3})\s*([EW])\b",
    re.IGNORECASE,
)

_RE_ALIQUOT = re.compile(
    r"\b(N½|S½|E½|W½|NE(?:/4|¼)?|NW(?:/4|¼)?|SE(?:/4|¼)?|SW(?:/4|¼)?|"
    r"N/2|S/2|E/2|W/2)\b",
    re.IGNORECASE,
)

_RE_LOTS = re.compile(
    r"\bLot[s]?\s+(\d+(?:\s*,\s*\d+)*)\b",
    re.IGNORECASE,
)

_RE_ACRES = re.compile(
    r"([\d,]+(?:\.\d+)?)\s*Acres?\b",
    re.IGNORECASE,
)

_RE_TEXAS_ABSTRACT = re.compile(
    r"\bA(?:bstract)?\.?\s*(?:No\.?\s*)?(\d+)\b|\bSurvey\s+(?:No\.?\s*)?(\w+)\b",
    re.IGNORECASE,
)

_RE_LOT_BLOCK = re.compile(
    r"\bLot\s+\w+.*?Block\s+\w+|\bBlock\s+\w+.*?Lot\s+\w+",
    re.IGNORECASE,
)

_RE_METES = re.compile(
    r"\bN\s*\d+[°º]\s*\d+[\'′]\s*[EW]\b|\bbeginning at\b|\bthence\b",
    re.IGNORECASE,
)

_QUARTER_NORMALIZE = {
    "n½": "N2", "s½": "S2", "e½": "E2", "w½": "W2",
    "n/2": "N2", "s/2": "S2", "e/2": "E2", "w/2": "W2",
    "ne/4": "NE", "nw/4": "NW", "se/4": "SE", "sw/4": "SW",
    "ne¼": "NE", "nw¼": "NW", "se¼": "SE", "sw¼": "SW",
}


def _normalize_quarter(raw: str) -> str:
    key = raw.lower().replace(" ", "")
    return _QUARTER_NORMALIZE.get(key, raw.upper().replace("/4", "").replace("¼", "").replace("½", "2").replace("/2", "2"))


def _parse_acres(text: str) -> Optional[float]:
    m = _RE_ACRES.search(text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _parse_aliquot_parts(text: str) -> list[AliquotPart]:
    """Parse all aliquot quarter-call chains from text."""
    parts: list[AliquotPart] = []

    # Split on comma or semicolon to handle compound descriptions
    # e.g. "NE/4 SW/4, NW/4 SE/4" → two AliquotParts
    # But "NE/4 of the SW/4" is one chain
    # Strategy: find all aliquot tokens in order, group by comma/semicolon breaks
    segments = re.split(r"[;,]|\band\b", text, flags=re.IGNORECASE)
    for seg in segments:
        tokens = _RE_ALIQUOT.findall(seg)
        if not tokens:
            # Check for lots
            lot_m = _RE_LOTS.search(seg)
            if lot_m:
                lot_nums = [int(x.strip()) for x in lot_m.group(1).split(",")]
                acres = _parse_acres(seg)
                parts.append(AliquotPart(quarters=[], lots=lot_nums, gross_acres=acres))
            continue
        quarters = [_normalize_quarter(t) for t in tokens]
        # Reverse so order is outermost-last (matching PLSS convention: NE/4 of SW/4 = SW first)
        # Input: "NE/4 SW/4" = NE quarter OF the SW quarter → stored as ['SW','NE']
        # We store in reading order and consumers reverse when rendering
        acres = _parse_acres(seg)
        parts.append(AliquotPart(quarters=quarters, gross_acres=acres))

    return parts


def parse_legal_description(desc: str) -> ParsedLegalDescription:
    """Parse a legal description string into a structured ParsedLegalDescription."""
    if not desc or not desc.strip():
        return ParsedLegalDescription(raw=desc or "", description_type="unknown")

    raw = desc.strip()
    result = ParsedLegalDescription(raw=raw)

    # --- Texas abstract detection (highest priority for TX) ---
    if _RE_TEXAS_ABSTRACT.search(raw) and not _RE_SEC.search(raw):
        result.description_type = "texas_abstract"
        result.is_plss = False
        # Try to extract abstract number
        m = re.search(r"A(?:bstract)?\.?\s*(?:No\.?\s*)?(\d+)", raw, re.IGNORECASE)
        if m:
            result.abstract_number = m.group(1)
        sm = re.search(r"Survey\s+(?:of\s+)?([A-Za-z][A-Za-z .]+?)(?:\s*,|\s*$|\s*in|\s*County)", raw, re.IGNORECASE)
        if sm:
            result.survey_name = sm.group(1).strip()
        result.parse_notes.append("Texas abstract / non-PLSS survey system — cannot render on PLSS grid")
        return result

    # --- Lot/Block detection ---
    if _RE_LOT_BLOCK.search(raw) and not _RE_SEC.search(raw):
        result.description_type = "lot_block"
        result.is_plss = False
        lm = re.search(r"Lot\s+(\w+)", raw, re.IGNORECASE)
        bm = re.search(r"Block\s+(\w+)", raw, re.IGNORECASE)
        sm_sub = re.search(r"(?:Subdivision|Addition)\s+(?:of\s+)?([A-Za-z][A-Za-z .]+?)(?:\s*,|\s*$)", raw, re.IGNORECASE)
        result.lot = lm.group(1) if lm else None
        result.block = bm.group(1) if bm else None
        result.subdivision = sm_sub.group(1).strip() if sm_sub else None
        result.parse_notes.append("Lot/Block subdivision description — not PLSS-mappable")
        return result

    # --- Metes and bounds detection ---
    if _RE_METES.search(raw) and not _RE_SEC.search(raw):
        result.description_type = "metes_bounds"
        result.is_plss = False
        result.parse_notes.append("Metes-and-bounds description — cannot render on PLSS grid")
        return result

    # --- PLSS parsing ---
    sec_matches = list(_RE_SEC.finditer(raw))
    twp_matches = list(_RE_TWP.finditer(raw))
    rng_matches = list(_RE_RNG.finditer(raw))

    if not sec_matches and not twp_matches:
        # Might still be a partial STR (aliquot only, no section call)
        aliquots = _parse_aliquot_parts(raw)
        if aliquots:
            result.description_type = "plss"
            result.is_plss = True
            ps = ParsedSection(aliquot_parts=aliquots, gross_acres=_parse_acres(raw))
            result.sections.append(ps)
            result.parse_notes.append("Aliquot parts found but no Section/Township/Range — partial PLSS")
        else:
            result.description_type = "unknown"
            result.parse_notes.append("Could not classify description")
        return result

    result.description_type = "plss"
    result.is_plss = True

    # Try to get the primary township/range (usually stated once for all sections)
    primary_twp_num = int(twp_matches[0].group(1)) if twp_matches else None
    primary_twp_dir = twp_matches[0].group(2).upper() if twp_matches else None
    primary_rng_num = int(rng_matches[0].group(1)) if rng_matches else None
    primary_rng_dir = rng_matches[0].group(2).upper() if rng_matches else None

    # For multi-section descriptions, split around section calls
    if len(sec_matches) > 1:
        # Process each section segment
        for i, sm in enumerate(sec_matches):
            sec_num = int(sm.group(1))
            # Text chunk for this section: from this match to next section match (or end)
            start = sm.start()
            end = sec_matches[i + 1].start() if i + 1 < len(sec_matches) else len(raw)
            chunk = raw[start:end]

            # Township/range for this section
            chunk_twp = _RE_TWP.search(chunk)
            chunk_rng = _RE_RNG.search(chunk)
            twp_num = int(chunk_twp.group(1)) if chunk_twp else primary_twp_num
            twp_dir = chunk_twp.group(2).upper() if chunk_twp else primary_twp_dir
            rng_num = int(chunk_rng.group(1)) if chunk_rng else primary_rng_num
            rng_dir = chunk_rng.group(2).upper() if chunk_rng else primary_rng_dir

            # Aliquot parts for this section — text before the Sec token
            aliquot_text = raw[:sm.start()] if i == 0 else raw[sec_matches[i - 1].end():sm.start()]
            aliquots = _parse_aliquot_parts(aliquot_text)
            if not aliquots:
                aliquots = _parse_aliquot_parts(chunk)

            ps = ParsedSection(
                section=sec_num,
                township_number=twp_num,
                township_dir=twp_dir,
                range_number=rng_num,
                range_dir=rng_dir,
                aliquot_parts=aliquots,
                gross_acres=_parse_acres(chunk),
            )
            result.sections.append(ps)
    else:
        # Single section
        sec_num = int(sec_matches[0].group(1)) if sec_matches else None
        aliquots = _parse_aliquot_parts(raw)
        gross_acres = _parse_acres(raw)

        ps = ParsedSection(
            section=sec_num,
            township_number=primary_twp_num,
            township_dir=primary_twp_dir,
            range_number=primary_rng_num,
            range_dir=primary_rng_dir,
            aliquot_parts=aliquots,
            gross_acres=gross_acres,
        )
        result.sections.append(ps)

    return result


# ---------------------------------------------------------------------------
# Grid geometry helpers
# ---------------------------------------------------------------------------

# Standard PLSS township: 6x6 grid, section 1 in the NORTHEAST corner.
# Even rows (0,2,4): numbered right-to-left (6→1, 18→13, 30→25)
# Odd rows  (1,3,5): numbered left-to-right (7→12, 19→24, 31→36)
_SECTION_GRID: dict[int, tuple[int, int]] = {}
for _row in range(6):
    for _col in range(6):
        if _row % 2 == 0:
            # Right-to-left: col 5 = lowest section number in this row
            _sec = _row * 6 + (5 - _col) + 1
        else:
            # Left-to-right: col 0 = lowest section number in this row
            _sec = _row * 6 + _col + 1
        _SECTION_GRID[_sec] = (_col, _row)   # (grid_x, grid_y)


def section_grid_position(section: int) -> Optional[tuple[int, int]]:
    """Return (col, row) 0-indexed position on the 6x6 PLSS grid, or None."""
    return _SECTION_GRID.get(section)


def aliquot_coverage_pct(parts: list[AliquotPart]) -> float:
    """
    Estimate the fraction of the section covered by the aliquot call.
    NE/4 = 0.25, N/2 = 0.5, NE/4 SW/4 = 0.0625, etc.
    Returns 0.0-1.0.
    """
    if not parts:
        return 1.0  # Whole section assumed if no aliquot given
    total = 0.0
    for part in parts:
        if part.lots and not part.quarters:
            # Government lots ≈ 40 ac each in a 640-ac section
            total += len(part.lots) * (40.0 / 640.0)
        else:
            frac = 1.0
            for q in part.quarters:
                if q in ("N2", "S2", "E2", "W2"):
                    frac *= 0.5
                elif q in ("NE", "NW", "SE", "SW"):
                    frac *= 0.25
            total += frac
    return min(total, 1.0)


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def parsed_to_dict(p: ParsedLegalDescription) -> dict:
    """Convert a ParsedLegalDescription to a JSON-safe dict for API responses."""
    return {
        "raw": p.raw,
        "is_plss": p.is_plss,
        "description_type": p.description_type,
        "parse_notes": p.parse_notes,
        "abstract_number": p.abstract_number,
        "survey_name": p.survey_name,
        "lot": p.lot,
        "block": p.block,
        "subdivision": p.subdivision,
        "sections": [
            {
                "section": s.section,
                "township_number": s.township_number,
                "township_dir": s.township_dir,
                "range_number": s.range_number,
                "range_dir": s.range_dir,
                "grid_position": section_grid_position(s.section) if s.section else None,
                "gross_acres": s.gross_acres,
                "coverage_pct": aliquot_coverage_pct(s.aliquot_parts),
                "aliquot_parts": [
                    {
                        "quarters": ap.quarters,
                        "lots": ap.lots,
                        "gross_acres": ap.gross_acres,
                    }
                    for ap in s.aliquot_parts
                ],
            }
            for s in p.sections
        ],
    }
