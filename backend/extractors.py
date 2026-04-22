from anthropic import Anthropic
from pydantic import BaseModel
from typing import Optional, List
import json

client = Anthropic()

class LeaseExtraction(BaseModel):
    lessor: Optional[str] = None
    lessee: Optional[str] = None
    legal_description: Optional[str] = None
    gross_acres: Optional[float] = None
    net_acres: Optional[float] = None
    royalty: Optional[float] = None
    primary_term: Optional[str] = None
    bonus: Optional[float] = None
    pugh_clauses: Optional[List[str]] = None
    depth_limits: Optional[str] = None
    shut_in: Optional[str] = None
    continuous_drilling: Optional[str] = None
    recording_date: Optional[str] = None

class DeedExtraction(BaseModel):
    grantor: Optional[str] = None
    grantee: Optional[str] = None
    legal_description: Optional[str] = None
    interest_conveyed: Optional[str] = None
    reservations: Optional[List[str]] = None
    date: Optional[str] = None
    recording_info: Optional[str] = None

class ExtractorPipeline:
    LEASE_PROMPT = """You are an expert oil & gas landman extracting structured data from lease documents.

Extract the following fields from the lease document text:
- lessor (primary lessor name)
- lessee (primary lessee/operator name)
- legal_description (legal description of property)
- gross_acres (total gross acreage)
- net_acres (net acreage to lessee)
- royalty (royalty percentage, e.g., 1/8, 12.5%)
- primary_term (primary lease term, e.g., "3 years", "5 years from effective date")
- bonus (signing bonus if any)
- pugh_clauses (list of any Pugh clause provisions)
- depth_limits (any depth or formation limits)
- shut_in (shut-in royalty clause if present)
- continuous_drilling (continuous drilling clause if present)
- recording_date (date lease was recorded)

Return ONLY valid JSON matching this exact structure, with null for missing fields."""

    DEED_PROMPT = """You are an expert oil & gas landman extracting structured data from deed documents.

Extract the following fields from the deed document text:
- grantor (person/entity conveying the property)
- grantee (person/entity receiving the property)
- legal_description (legal description of property)
- interest_conveyed (what fractional or other interest is conveyed, e.g., "1/2 interest in and to all oil, gas, and mineral rights")
- reservations (list of any reserved interests, e.g., "subject to all outstanding oil and gas leases")
- date (date of the deed)
- recording_info (county, state, recording date/book/page if present)

Return ONLY valid JSON matching this exact structure, with null for missing fields."""

    @staticmethod
    def extract_lease(document_text: str) -> LeaseExtraction:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": f"{ExtractorPipeline.LEASE_PROMPT}\n\nDocument:\n{document_text}"}
            ]
        )

        content = response.content[0].text
        try:
            data = json.loads(content)
            return LeaseExtraction(**data)
        except (json.JSONDecodeError, ValueError):
            return LeaseExtraction()

    @staticmethod
    def extract_deed(document_text: str) -> DeedExtraction:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": f"{ExtractorPipeline.DEED_PROMPT}\n\nDocument:\n{document_text}"}
            ]
        )

        content = response.content[0].text
        try:
            data = json.loads(content)
            return DeedExtraction(**data)
        except (json.JSONDecodeError, ValueError):
            return DeedExtraction()
