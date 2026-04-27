"""Sanitizer for extractor field values — drops form labels and truncates field bleed."""

from extractors import (
    DeedExtraction,
    LeaseExtraction,
    _sanitize_deed,
    _sanitize_field,
    _sanitize_lease,
)


def test_pure_label_with_colon_returns_none():
    assert _sanitize_field("Original Lessee:") is None
    assert _sanitize_field("Recording Information:") is None
    assert _sanitize_field("Lessor:") is None
    assert _sanitize_field("Grantor:") is None


def test_pure_label_without_colon_returns_none():
    assert _sanitize_field("Original Lessee") is None
    assert _sanitize_field("Recording Information") is None


def test_label_prefix_drops_value():
    # If the model returns "Lessor: John Smith", we'd rather drop it than try to
    # recover. The strengthened prompt should make this case rare.
    assert _sanitize_field("Lessor: John Smith") is None


def test_field_bleed_truncates_at_label_boundary():
    # Real bug from tx-glo-lease-1063833.pdf: lessor names followed by next form field.
    bled = "Herd , John Tevis , John Jason Sullivan and C. Boyd Finch Leaso Date: 6/24/2009 Ut J"
    assert (
        _sanitize_field(bled)
        == "Herd , John Tevis , John Jason Sullivan and C. Boyd Finch"
    )
    assert _sanitize_field("John Smith  Lease Date: 6/24/2009") == "John Smith"
    assert _sanitize_field("Smith Original Lessee: EOG") == "Smith"


def test_real_values_preserved():
    assert _sanitize_field("EOG Resources, Inc.") == "EOG Resources, Inc."
    assert (
        _sanitize_field("Commissioner of the General Land Office of the State of Texas")
        == "Commissioner of the General Land Office of the State of Texas"
    )
    assert (
        _sanitize_field("PIONEER NATURAL RESOURCES USA, INC.")
        == "PIONEER NATURAL RESOURCES USA, INC."
    )


def test_legal_descriptions_not_clobbered():
    # Words like "Volume", "Page", "Section", "Block" appear inside legal
    # descriptions and must be kept. They are intentionally excluded from the
    # form-label list.
    legal_a = "Volume 484, Page 274, Deed Records of La Salle County, Texas"
    legal_b = "Tracts 1, 1A, 3, 6, 7, 8, 9, 10, 11 & 14"
    legal_c = "Section 14, Block 2, T&P Ry Co Survey"
    assert _sanitize_field(legal_a) == legal_a
    assert _sanitize_field(legal_b) == legal_b
    assert _sanitize_field(legal_c) == legal_c


def test_empty_and_none_inputs():
    assert _sanitize_field(None) is None
    assert _sanitize_field("") is None
    assert _sanitize_field("   ") is None


def test_non_string_passthrough():
    # Numeric / list fields go through other code paths; sanitizer should not
    # mangle non-strings if it ever sees one.
    assert _sanitize_field(123) == 123  # type: ignore[arg-type]


def test_sanitize_lease_drops_label_lessor_lessee():
    le = LeaseExtraction(lessor="Original Lessee:", lessee="Recording Information:")
    out = _sanitize_lease(le)
    assert out.lessor is None
    assert out.lessee is None


def test_sanitize_lease_truncates_bleed_and_keeps_real_values():
    le = LeaseExtraction(
        lessor="John Smith Lease Date: 6/24/2009",
        lessee="EOG Resources, Inc.",
        legal_description="Section 14, Block 2",
        royalty="1/8",
        primary_term="3 years",
    )
    out = _sanitize_lease(le)
    assert out.lessor == "John Smith"
    assert out.lessee == "EOG Resources, Inc."
    assert out.legal_description == "Section 14, Block 2"
    assert out.royalty == "1/8"
    assert out.primary_term == "3 years"


def test_sanitize_deed_applies_same_rules():
    de = DeedExtraction(
        grantor="Grantor:",
        grantee="EOG Resources, Inc.",
        legal_description="Tract 1",
        interest_conveyed="100% working interest Recording Date: 2020-01-01",
    )
    out = _sanitize_deed(de)
    assert out.grantor is None
    assert out.grantee == "EOG Resources, Inc."
    assert out.legal_description == "Tract 1"
    assert out.interest_conveyed == "100% working interest"
