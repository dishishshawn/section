import json
import os
import re
from datetime import datetime, timedelta
from typing import Optional, List
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy.orm import Session

from models import Tract, Party, Instrument, Interest, Obligation, Document

try:
    from anthropic import Anthropic

    _client: Optional[Anthropic] = None

    def _get_client() -> Optional[Anthropic]:
        global _client
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key or key.startswith("your_"):
            return None
        if _client is None:
            base_url = os.getenv("ANTHROPIC_BASE_URL")
            kwargs = {"api_key": key}
            if base_url:
                kwargs["base_url"] = base_url
            _client = Anthropic(**kwargs)
        return _client

except ImportError:

    def _get_client():
        return None


CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")


class LeaseExtraction(BaseModel):
    lessor: Optional[str] = None
    lessee: Optional[str] = None
    legal_description: Optional[str] = None
    gross_acres: Optional[float] = None
    net_acres: Optional[float] = None
    royalty: Optional[str] = None
    primary_term: Optional[str] = None
    bonus: Optional[float] = None
    pugh_clauses: Optional[List[str]] = None
    depth_limits: Optional[str] = None
    shut_in: Optional[str] = None
    continuous_drilling: Optional[str] = None
    recording_date: Optional[str] = None
    effective_date: Optional[str] = None
    source_quotes: Optional[dict] = None
    source_pages: Optional[dict] = None


class DeedExtraction(BaseModel):
    grantor: Optional[str] = None
    grantee: Optional[str] = None
    legal_description: Optional[str] = None
    interest_conveyed: Optional[str] = None
    fraction_numerator: Optional[int] = None
    fraction_denominator: Optional[int] = None
    mineral_estate: Optional[str] = None
    reservations: Optional[List[str]] = None
    date: Optional[str] = None
    recording_info: Optional[str] = None
    source_quotes: Optional[dict] = None
    source_pages: Optional[dict] = None


LEASE_PROMPT = """You are an expert oil & gas landman extracting structured data from a lease.

Return ONLY a JSON object with these keys (use null for missing fields):
{
  "lessor": string,
  "lessee": string,
  "legal_description": string,
  "gross_acres": number,
  "net_acres": number,
  "royalty": string (e.g., "1/8", "3/16", "20%"),
  "primary_term": string (e.g., "3 years"),
  "bonus": number,
  "pugh_clauses": [string],
  "depth_limits": string,
  "shut_in": string,
  "continuous_drilling": string,
  "recording_date": string (YYYY-MM-DD),
  "effective_date": string (YYYY-MM-DD),
  "source_quotes": {
    "lessor": string (excerpt from document supporting lessor, max 200 chars),
    "lessee": string,
    "legal_description": string,
    "gross_acres": string,
    "royalty": string,
    "primary_term": string,
    "effective_date": string
  },
  "source_pages": {
    "lessor": integer (page number where the lessor quote appears),
    "lessee": integer,
    "legal_description": integer,
    "gross_acres": integer,
    "royalty": integer,
    "primary_term": integer,
    "effective_date": integer
  }
}

The document text is segmented with [PAGE N] markers — one per page. For
source_pages, return the integer N of the page where each quote appears. If a
field spans multiple pages, return the page where the supporting quote starts.

Rules for the FIELD VALUES (lessor, lessee, legal_description, etc.):
- NEVER return a form label as a value. If the only thing visible is a heading
  like "Lessor:", "Original Lessee:", "Recording Information:", or
  "Lease Date:" with no nearby content, return null for that field.
- NEVER bleed multiple fields into one value. If a lessor's name is followed
  by another label (e.g. "...C. Boyd Finch  Lease Date: 6/24/2009..."), stop
  the lessor value before that label. The value should contain ONLY the answer
  to its own field.
- Two-column form layouts often appear in extracted text as a column of bare
  labels followed (much later) by a column of values. If you cannot confidently
  match a label to its value, return null rather than guessing.

For source_quotes:
- Return the SUBSTANTIVE clause that contains the actual answer, NOT a heading
  or label. Bad: "Lessor:" or "Original Lessee:". Good: the full sentence or
  phrase identifying the lessor by name (e.g., "...the Commissioner of the
  General Land Office of the State of Texas...").
- The quote must, on its own, justify the field value to a reader who has not
  seen the rest of the document.
- Prefer verbatim. Minor OCR noise is acceptable. NEVER return null when the
  corresponding field has a value.
- Aim for 60-200 characters. A two-word fragment is unacceptable unless that
  fragment IS the answer.

Document:
"""

DEED_PROMPT = """You are an expert oil & gas landman extracting structured data from a deed.

Return ONLY a JSON object with these keys (use null for missing fields):
{
  "grantor": string,
  "grantee": string,
  "legal_description": string,
  "interest_conveyed": string,
  "fraction_numerator": integer,
  "fraction_denominator": integer,
  "mineral_estate": string,
  "reservations": [string],
  "date": string (YYYY-MM-DD),
  "recording_info": string,
  "source_quotes": {
    "grantor": string (excerpt from document, max 200 chars),
    "grantee": string,
    "legal_description": string,
    "interest_conveyed": string,
    "date": string
  },
  "source_pages": {
    "grantor": integer,
    "grantee": integer,
    "legal_description": integer,
    "interest_conveyed": integer,
    "date": integer
  }
}

The document text is segmented with [PAGE N] markers — one per page. For
source_pages, return the integer N where each quote appears.

Rules for the FIELD VALUES (grantor, grantee, legal_description, etc.):
- NEVER return a form label as a value. If the only thing visible is a heading
  like "Grantor:", "Grantee:", or "Date:" with no nearby content, return null
  for that field.
- NEVER bleed multiple fields into one value. If a grantor's name is followed
  by another label (e.g. "...John Smith  Date: 6/24/2009..."), stop the value
  before that label. The value should contain ONLY the answer to its own field.
- If you cannot confidently match a label to its value, return null rather than
  guessing.

For source_quotes:
- Return the SUBSTANTIVE clause that contains the actual answer, NOT a heading
  or label. Bad: "Grantor:" or "Date:". Good: the full phrase identifying the
  party by name or stating the date inline.
- The quote must, on its own, justify the field value.
- Prefer verbatim; minor OCR noise is acceptable. NEVER return null when the
  corresponding field has a value.
- Aim for 60-200 characters. A two-word fragment is unacceptable unless that
  fragment IS the answer.

Document:
"""


def _ocr_pdf_text(path: Path) -> str:
    # OCR fallback for scanned/image-only PDFs. Renders each page with pypdfium2
    # and runs Tesseract via pytesseract. Requires the Tesseract binary on PATH
    # (TESSERACT_CMD env var overrides). Disable entirely with ENABLE_OCR=0.
    if os.getenv("ENABLE_OCR", "1") == "0":
        return ""
    try:
        import pypdfium2 as pdfium
        import pytesseract
        from PIL import Image  # noqa: F401  (ensures Pillow present)
    except ImportError:
        return ""

    tesseract_cmd = os.getenv("TESSERACT_CMD")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    dpi = int(os.getenv("OCR_DPI", "200"))
    scale = dpi / 72.0
    max_pages = int(os.getenv("OCR_MAX_PAGES", "50"))

    pages_out = []
    pdf = pdfium.PdfDocument(str(path))
    try:
        for i, page in enumerate(pdf):
            if i >= max_pages:
                break
            pil_image = page.render(scale=scale).to_pil()
            try:
                page_text = pytesseract.image_to_string(pil_image) or ""
            finally:
                pil_image.close()
            pages_out.append(f"[PAGE {i + 1}]\n{page_text.strip()}")
    finally:
        pdf.close()
    return "\n\n".join(pages_out).strip()


def extract_pdf_text(path: Path) -> str:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))

        pages_text = "\n\n".join(
            f"[PAGE {idx + 1}]\n{(page.extract_text() or '').strip()}" for idx, page in enumerate(reader.pages)
        )

        fields = reader.get_fields() or {}
        filled_fields = []
        for name, data in fields.items():
            if not isinstance(data, dict):
                continue
            value = data.get("/V")
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            filled_fields.append(f"{name}: {value}")

        # If the PDF is an AcroForm and no field has a value, treat as unfilled template
        # regardless of any boilerplate/instructions text in the document body.
        if fields and not filled_fields:
            return "[EMPTY_FORM_TEMPLATE]"

        parts = []
        if filled_fields:
            parts.append("FORM FIELDS:\n" + "\n".join(filled_fields))
        meaningful_text = "".join(c for c in pages_text if not c.isspace())
        if meaningful_text:
            parts.append("DOCUMENT TEXT:\n" + pages_text)

        # Scanned PDF: no embedded text and no AcroForm. Fall back to OCR.
        if not parts and not fields:
            try:
                ocr_text = _ocr_pdf_text(path)
            except Exception as e:
                return f"[PDF extraction failed: OCR error: {e}]"
            if ocr_text:
                parts.append("DOCUMENT TEXT (OCR):\n" + ocr_text)

        return "\n\n".join(parts) if parts else ""
    except Exception as e:
        return f"[PDF extraction failed: {e}]"


def extract_text(path: Path, mime: Optional[str]) -> str:
    if path.suffix.lower() == ".pdf" or (mime and "pdf" in mime):
        return extract_pdf_text(path)
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def classify_document(filename: str, text: str) -> str:
    name = filename.lower()
    head = (text or "")[:2000].lower()
    title = (text or "").lstrip().split("\n", 1)[0].lower()

    # 1. Filename is strongest signal
    if "assignment" in name:
        return "assignment"
    if "deed" in name:
        return "deed"
    if "lease" in name:
        return "lease"

    # 2. Document title (first line) is next strongest
    if "assignment" in title:
        return "assignment"
    if "deed" in title:
        return "deed"
    if "lease" in title:
        return "lease"

    # 3. Fall back to content keywords
    if "lessor" in head and "lessee" in head:
        return "lease"
    if "grantor" in head and "grantee" in head:
        return "deed"
    if "assignor" in head and "assignee" in head:
        return "assignment"

    return "lease"


def _log(msg: str) -> None:
    print(f"[extractor] {msg}", flush=True)


def _extract_json_from_response(content: str) -> Optional[dict]:
    # Strip markdown code fences if present
    fence_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", content)
    if fence_match:
        candidate = fence_match.group(1)
    else:
        # Take the outermost JSON object: first { through last }
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end < start:
            return None
        candidate = content[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


_OCR_LENIENCE_NOTE = (
    "\nNOTE: The document text below was produced by OCR and may contain "
    "artifacts (broken words, line breaks, mis-recognized characters, "
    "extra spacing). Quote the closest matching span — minor OCR noise is "
    "acceptable and expected. Do NOT return null for a source_quote just "
    "because the OCR text is imperfect. The [PAGE N] markers are reliable "
    "and should still be used for source_pages.\n"
)


def _call_claude(prompt: str, text: str) -> Optional[dict]:
    client = _get_client()
    if client is None:
        _log("Claude client not configured (ANTHROPIC_API_KEY missing/placeholder)")
        return None
    is_ocr = "DOCUMENT TEXT (OCR):" in text[:200]
    effective_prompt = prompt + (_OCR_LENIENCE_NOTE if is_ocr else "")
    try:
        _log(f"calling Claude model={CLAUDE_MODEL} base={os.getenv('ANTHROPIC_BASE_URL') or 'default'} ocr={is_ocr}")
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            system="You are a JSON-only extraction tool. Respond with ONLY a valid JSON object. No prose, no markdown fences, no explanations.",
            messages=[
                {"role": "user", "content": effective_prompt + text[:20000]},
                {"role": "assistant", "content": "{"},
            ],
        )
        raw = response.content[0].text
        content = "{" + raw
        _log(f"Claude returned {len(content)} chars: {content[:120]!r}")
        parsed = _extract_json_from_response(content)
        if parsed is None:
            _log(f"JSON parse failed; full content={content[:500]!r}")
        return parsed
    except Exception as e:
        _log(f"Claude call failed: {type(e).__name__}: {e}")
    return None


# Form labels that the model sometimes returns verbatim (as a value) or that
# bleed into the end of a real value when two-column form layouts collapse during
# PDF text extraction. Used to drop label-only values and truncate field bleed.
# Keep this list narrow: tokens here must be unambiguous form labels, not words
# that legitimately appear inside a value (e.g. "Section", "Block", "County",
# "Volume", "Page" all show up inside legal descriptions and are excluded).
_FORM_LABELS = (
    "Lessor",
    "Lessee",
    "Original Lessee",
    "Recording Information",
    "Recording Info",
    "Lease Date",
    "Leaso Date",  # common OCR noise for "Lease Date"
    "Effective Date",
    "Recording Date",
    "Primary Term",
    "Royalty",
    "Bonus",
    "Grantor",
    "Grantee",
    "Assignor",
    "Assignee",
    "EOG Lease Number",
    "Lease Number",
    "Unit Plat Number",
    "Land Part",
)

_LABEL_BOUNDARY_RE = re.compile(
    r"(?:^|\s+)(?:" + "|".join(re.escape(t) for t in _FORM_LABELS) + r")\s*:",
    re.IGNORECASE,
)

_LABEL_ONLY_VALUES = frozenset(t.lower() for t in _FORM_LABELS)


def _sanitize_field(value: Optional[str]) -> Optional[str]:
    # Drop label-only values and truncate field bleed (e.g. a lessor name
    # followed by "Lease Date: 6/24/2009"). Returns None if the cleaned value
    # is empty or matches a known form label.
    if not isinstance(value, str):
        return value
    cleaned = value.strip()
    if not cleaned:
        return None

    match = _LABEL_BOUNDARY_RE.search(cleaned)
    if match:
        cleaned = cleaned[:match.start()].rstrip(" ,;-")

    bare = cleaned.rstrip(":").strip()
    if not bare:
        return None
    if bare.lower() in _LABEL_ONLY_VALUES:
        return None
    if cleaned.endswith(":") and " " not in bare:
        # Single-token value ending in colon is almost certainly a stray label.
        return None
    return cleaned


def _sanitize_lease(le: LeaseExtraction) -> LeaseExtraction:
    le.lessor = _sanitize_field(le.lessor)
    le.lessee = _sanitize_field(le.lessee)
    le.legal_description = _sanitize_field(le.legal_description)
    le.royalty = _sanitize_field(le.royalty)
    le.primary_term = _sanitize_field(le.primary_term)
    le.depth_limits = _sanitize_field(le.depth_limits)
    le.shut_in = _sanitize_field(le.shut_in)
    le.continuous_drilling = _sanitize_field(le.continuous_drilling)
    return le


def _sanitize_deed(de: DeedExtraction) -> DeedExtraction:
    de.grantor = _sanitize_field(de.grantor)
    de.grantee = _sanitize_field(de.grantee)
    de.legal_description = _sanitize_field(de.legal_description)
    de.interest_conveyed = _sanitize_field(de.interest_conveyed)
    de.mineral_estate = _sanitize_field(de.mineral_estate)
    de.recording_info = _sanitize_field(de.recording_info)
    return de


def _regex_lease_fallback(text: str) -> LeaseExtraction:
    def grab(pattern: str, flags=re.IGNORECASE) -> Optional[str]:
        m = re.search(pattern, text, flags)
        return m.group(1).strip() if m else None

    lessor = grab(r"LESSOR:\s*([^\n]+)")
    lessee = grab(r"LESSEE:\s*([^\n]+)")
    legal = grab(r"LEGAL DESCRIPTION:\s*\n?([^\n]+(?:\n[^\n:]+)?)")
    acres_str = grab(r"containing\s+([\d,\.]+)\s*acres")
    royalty = grab(r"Royalty:\s*([^\n,]+)")
    term = grab(r"Primary Term:\s*([^\n]+)")
    bonus_str = grab(r"Bonus:\s*\$?([\d,\.]+)")
    pugh = grab(r"(Pugh Clause[^\n]*)")
    depth = grab(r"Depth Limits?:\s*([^\n]+)")
    continuous = grab(r"Continuous Drilling:\s*([^\n]+)")
    shutin = grab(r"Shut-in[^:]*:\s*([^\n]+)")
    eff_date = grab(r"Effective Date:\s*([^\n]+)")
    rec_date = grab(r"Recording Date:\s*([^\n]+)")

    def normalize_date(s: Optional[str]) -> Optional[str]:
        if not s:
            return None
        for fmt in ("%B %d, %Y", "%m/%d/%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(s.strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    return LeaseExtraction(
        lessor=lessor,
        lessee=lessee,
        legal_description=legal.strip() if legal else None,
        gross_acres=float(acres_str.replace(",", "")) if acres_str else None,
        royalty=royalty,
        primary_term=term,
        bonus=float(bonus_str.replace(",", "")) if bonus_str else None,
        pugh_clauses=[pugh] if pugh else None,
        depth_limits=depth,
        shut_in=shutin,
        continuous_drilling=continuous,
        effective_date=normalize_date(eff_date),
        recording_date=normalize_date(rec_date),
    )


def _regex_deed_fallback(text: str) -> DeedExtraction:
    def grab(pattern: str, flags=re.IGNORECASE) -> Optional[str]:
        m = re.search(pattern, text, flags)
        return m.group(1).strip() if m else None

    grantor = grab(r"GRANTOR:\s*([^\n]+)")
    grantee = grab(r"GRANTEE:\s*([^\n]+)")
    legal = grab(r"LEGAL DESCRIPTION:\s*\n?([^\n]+(?:\n[^\n:]+)?)")
    interest = grab(r"Interest Conveyed:\s*([^\n]+)")
    mineral = grab(r"Mineral Estate:\s*([^\n]+)")
    fraction = grab(r"(\d+)\s*/\s*(\d+)\s*interest")

    num = denom = None
    if fraction:
        m = re.search(r"(\d+)\s*/\s*(\d+)", fraction)
        if m:
            num, denom = int(m.group(1)), int(m.group(2))

    return DeedExtraction(
        grantor=grantor,
        grantee=grantee,
        legal_description=legal.strip() if legal else None,
        interest_conveyed=interest,
        fraction_numerator=num,
        fraction_denominator=denom,
        mineral_estate=mineral,
    )


def extract_lease(text: str) -> LeaseExtraction:
    data = _call_claude(LEASE_PROMPT, text)
    if data:
        lease = LeaseExtraction(**{k: v for k, v in data.items() if k in LeaseExtraction.model_fields})
    else:
        lease = _regex_lease_fallback(text)
    return _sanitize_lease(lease)


def extract_deed(text: str) -> DeedExtraction:
    data = _call_claude(DEED_PROMPT, text)
    if data:
        deed = DeedExtraction(**{k: v for k, v in data.items() if k in DeedExtraction.model_fields})
    else:
        deed = _regex_deed_fallback(text)
    return _sanitize_deed(deed)


def _get_or_create_party(db: Session, project_id: int, name: str, ptype: str = "entity") -> Party:
    if not name:
        return None
    party = db.query(Party).filter(Party.project_id == project_id, Party.name == name).first()
    if party:
        return party
    party = Party(project_id=project_id, name=name, type=ptype)
    db.add(party)
    db.flush()
    return party


def _get_or_create_tract(
    db: Session, project_id: int, legal_desc: Optional[str], gross_acres: Optional[float]
) -> Tract:
    tract = None
    if legal_desc:
        tract = (
            db.query(Tract)
            .filter(
                Tract.project_id == project_id,
                Tract.legal_description == legal_desc,
            )
            .first()
        )
    if tract:
        if gross_acres and not tract.gross_acres:
            tract.gross_acres = gross_acres
        return tract
    tract = Tract(
        project_id=project_id,
        legal_description=legal_desc or "Unspecified tract",
        gross_acres=gross_acres,
    )
    db.add(tract)
    db.flush()
    return tract


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def materialize_lease(db: Session, project_id: int, document_id: int, lease: LeaseExtraction) -> None:
    if not lease.lessor and not lease.lessee and not lease.legal_description:
        _log("lease extraction empty - skipping materialization")
        return
    tract = _get_or_create_tract(db, project_id, lease.legal_description, lease.gross_acres)
    lessor_party = _get_or_create_party(db, project_id, lease.lessor or "", "individual")
    _get_or_create_party(db, project_id, lease.lessee or "", "entity")

    effective = _parse_date(lease.effective_date) or _parse_date(lease.recording_date)
    inst = Instrument(
        project_id=project_id,
        type="lease",
        recorded_at=_parse_date(lease.recording_date) or effective,
        source_document_id=document_id,
        extracted_data={
            "lessor": lease.lessor,
            "lessee": lease.lessee,
            "royalty": lease.royalty,
            "primary_term": lease.primary_term,
            "bonus": lease.bonus,
            "pugh_clauses": lease.pugh_clauses,
            "depth_limits": lease.depth_limits,
            "source_quotes": lease.source_quotes or {},
            "source_pages": lease.source_pages or {},
        },
    )
    db.add(inst)
    db.flush()

    if lessor_party and tract:
        existing = (
            db.query(Interest)
            .filter(
                Interest.tract_id == tract.id,
                Interest.party_id == lessor_party.id,
            )
            .first()
        )
        if not existing:
            burdens = {"royalty_to_lessee": lease.royalty} if lease.royalty else None
            db.add(
                Interest(
                    tract_id=tract.id,
                    party_id=lessor_party.id,
                    fraction_numerator=1,
                    fraction_denominator=1,
                    mineral_estate=f"Minerals leased to {lease.lessee}" if lease.lessee else "Minerals",
                    burdens=burdens,
                )
            )

    term_days = _parse_primary_term_days(lease.primary_term)
    base = effective or datetime.utcnow()
    if term_days:
        db.add(
            Obligation(
                project_id=project_id,
                instrument_id=inst.id,
                type="primary_term_expiration",
                due_date=base + timedelta(days=term_days),
                params={"description": f"Primary term ({lease.primary_term}) expires"},
            )
        )
    if lease.continuous_drilling:
        db.add(
            Obligation(
                project_id=project_id,
                instrument_id=inst.id,
                type="continuous_drilling",
                due_date=datetime.utcnow() + timedelta(days=90),
                params={"description": lease.continuous_drilling},
            )
        )
    if lease.pugh_clauses:
        db.add(
            Obligation(
                project_id=project_id,
                instrument_id=inst.id,
                type="pugh_trigger",
                due_date=(base + timedelta(days=term_days)) if term_days else (datetime.utcnow() + timedelta(days=180)),
                params={"description": "Pugh clause release trigger at end of primary term"},
            )
        )


def materialize_deed(db: Session, project_id: int, document_id: int, deed: DeedExtraction) -> None:
    if not deed.grantor and not deed.grantee and not deed.legal_description:
        _log("deed extraction empty - skipping materialization")
        return
    tract = _get_or_create_tract(db, project_id, deed.legal_description, None)
    grantor = _get_or_create_party(db, project_id, deed.grantor or "", "individual")
    grantee = _get_or_create_party(db, project_id, deed.grantee or "", "entity")

    db.add(
        Instrument(
            project_id=project_id,
            type="warranty_deed",
            recorded_at=_parse_date(deed.date),
            source_document_id=document_id,
            extracted_data={
                "grantor": deed.grantor,
                "grantee": deed.grantee,
                "interest_conveyed": deed.interest_conveyed,
                "reservations": deed.reservations,
                "mineral_estate": deed.mineral_estate,
                "source_quotes": deed.source_quotes or {},
                "source_pages": deed.source_pages or {},
            },
        )
    )

    if grantee and deed.fraction_numerator and deed.fraction_denominator:
        db.add(
            Interest(
                tract_id=tract.id,
                party_id=grantee.id,
                fraction_numerator=deed.fraction_numerator,
                fraction_denominator=deed.fraction_denominator,
                mineral_estate=deed.mineral_estate or "Minerals Only",
                burdens=deed.reservations or None,
            )
        )


def _parse_primary_term_days(term: Optional[str]) -> Optional[int]:
    if not term:
        return None
    match = re.search(r"(\d+)\s*(year|yr|month|day)", term.lower())
    if not match:
        return None
    n, unit = int(match.group(1)), match.group(2)
    if unit.startswith("year") or unit == "yr":
        return n * 365
    if unit.startswith("month"):
        return n * 30
    return n


ASSIGNMENT_PROMPT = """You are an expert oil & gas landman extracting structured data from an assignment of oil and gas lease.

Return ONLY a JSON object with these keys (use null for missing):
{
  "grantor": string (the Assignor),
  "grantee": string (the Assignee),
  "legal_description": string,
  "interest_conveyed": string (e.g., "100% working interest"),
  "date": string (YYYY-MM-DD, the effective date),
  "recording_info": string,
  "source_quotes": {
    "grantor": string (excerpt from document, max 200 chars),
    "grantee": string,
    "legal_description": string,
    "date": string
  },
  "source_pages": {
    "grantor": integer,
    "grantee": integer,
    "legal_description": integer,
    "date": integer
  }
}

The document text is segmented with [PAGE N] markers — one per page. For
source_pages, return the integer N where each quote appears.

Rules for the FIELD VALUES (grantor, grantee, legal_description, etc.):
- NEVER return a form label as a value. If the only thing visible is a heading
  like "Assignor:", "Assignee:", or "Date:" with no nearby content, return
  null for that field.
- NEVER bleed multiple fields into one value. If a party's name is followed by
  another label, stop the value before that label.
- If you cannot confidently match a label to its value, return null rather than
  guessing.

For source_quotes:
- Return the SUBSTANTIVE clause that contains the actual answer, NOT a heading
  or label. Bad: "Grantor:" or "Date:". Good: the full phrase identifying the
  party by name or stating the date inline.
- The quote must, on its own, justify the field value.
- Prefer verbatim; minor OCR noise is acceptable. NEVER return null when the
  corresponding field has a value.
- Aim for 60-200 characters. A two-word fragment is unacceptable unless that
  fragment IS the answer.

Document:
"""


def extract_assignment(text: str) -> DeedExtraction:
    data = _call_claude(ASSIGNMENT_PROMPT, text)
    if data:
        assignment = DeedExtraction(**{k: v for k, v in data.items() if k in DeedExtraction.model_fields})
    else:
        assignment = _regex_deed_fallback(text)
    return _sanitize_deed(assignment)


def materialize_assignment(db: Session, project_id: int, document_id: int, assignment: DeedExtraction) -> None:
    if not assignment.grantor and not assignment.grantee and not assignment.legal_description:
        _log("assignment extraction empty - skipping materialization")
        return
    tract = _get_or_create_tract(db, project_id, assignment.legal_description, None)
    _get_or_create_party(db, project_id, assignment.grantor or "", "entity")
    _get_or_create_party(db, project_id, assignment.grantee or "", "entity")

    db.add(
        Instrument(
            project_id=project_id,
            type="assignment",
            recorded_at=_parse_date(assignment.date),
            source_document_id=document_id,
            extracted_data={
                "grantor": assignment.grantor,
                "grantee": assignment.grantee,
                "interest_conveyed": assignment.interest_conveyed,
                "source_quotes": assignment.source_quotes or {},
                "source_pages": assignment.source_pages or {},
            },
        )
    )


def process_document(db: Session, document: Document, file_path: Path) -> dict:
    text = extract_text(file_path, document.mime)

    if text == "[EMPTY_FORM_TEMPLATE]":
        document.ocr_status = "complete"
        document.extraction_status = "skipped: unfilled form template"
        db.commit()
        _log(f"{file_path.name} is a blank form template - skipping extraction")
        return {"status": "skipped", "reason": "unfilled_form_template"}

    if not text or text.startswith("[PDF extraction failed"):
        document.ocr_status = "failed"
        document.extraction_status = "failed: no text extracted"
        db.commit()
        _log(f"{file_path.name} produced no extractable text (likely scanned image)")
        return {"status": "failed", "reason": "no_text"}

    doc_type = classify_document(file_path.name, text)
    document.ocr_status = "complete"
    document.extraction_status = "in_progress"
    db.commit()

    try:
        if doc_type == "lease":
            lease = extract_lease(text)
            materialize_lease(db, document.project_id, document.id, lease)
        elif doc_type == "deed":
            deed = extract_deed(text)
            materialize_deed(db, document.project_id, document.id, deed)
        elif doc_type == "assignment":
            assignment = extract_assignment(text)
            materialize_assignment(db, document.project_id, document.id, assignment)
        else:
            deed = extract_deed(text)
            materialize_deed(db, document.project_id, document.id, deed)

        document.extraction_status = "complete"
        db.commit()
        return {"status": "complete", "doc_type": doc_type, "used_claude": _get_client() is not None}
    except Exception as e:
        document.extraction_status = f"failed: {e}"
        db.commit()
        raise
