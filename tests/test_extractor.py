"""Unit tests for P2 — Document Extractor.

Covers:
  - compute_ais_diff detects the FD interest trap in Priya's data
  - No false mismatches for fully-declared income (Rajan)
  - Mismatch amounts match expected values from the problem statement
  - TaxpayerProfile model validation (field types, computed total)
  - extractor_node returns correct state shape (mocked LLM)

Run with:  pytest tests/test_extractor.py -v
"""

import pytest
from unittest.mock import MagicMock, patch

from extractor.models import (
    AIS,
    AISMismatchReport,
    DeclaredByTaxpayer,
    Form16,
    MismatchItem,
    Sec80C,
    TaxpayerProfile,
)
from extractor.diff import compute_ais_diff
from extractor.sample_data import PRIYA_PROFILE, RAJAN_PROFILE, ANKUR_PROFILE
from extractor.extractor import extractor_node


# ---------------------------------------------------------------------------
# compute_ais_diff — Priya (main test case)
# ---------------------------------------------------------------------------

class TestPriyaDiff:
    """Priya Sharma: FD interest ₹38,000 in AIS, ₹0 declared — the deliberate trap."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.report = compute_ais_diff(PRIYA_PROFILE)

    def test_has_mismatches(self):
        assert self.report.has_mismatches is True

    def test_mismatch_count(self):
        assert len(self.report.mismatches) == 1

    def test_fd_interest_flagged(self):
        m = self.report.mismatches[0]
        assert m.income_type == "fd_interest"

    def test_fd_interest_ais_amount(self):
        m = self.report.mismatches[0]
        assert m.ais_amount == 38_000

    def test_fd_interest_declared_amount(self):
        m = self.report.mismatches[0]
        assert m.declared_amount == 0

    def test_fd_interest_difference(self):
        m = self.report.mismatches[0]
        assert m.difference == 38_000

    def test_total_undeclared_income(self):
        assert self.report.total_undeclared_income == 38_000

    def test_savings_interest_not_flagged(self):
        """Savings interest matches (both 12,000) — must not appear in mismatches."""
        types = [m.income_type for m in self.report.mismatches]
        assert "savings_interest" not in types

    def test_description_contains_amount(self):
        m = self.report.mismatches[0]
        assert "38,000" in m.description


# ---------------------------------------------------------------------------
# compute_ais_diff — Rajan (no mismatches expected)
# ---------------------------------------------------------------------------

class TestRajanDiff:
    """Rajan Iyer: declared FD interest matches AIS — no mismatches."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.report = compute_ais_diff(RAJAN_PROFILE)

    def test_no_mismatches(self):
        assert self.report.has_mismatches is False

    def test_zero_undeclared(self):
        assert self.report.total_undeclared_income == 0


# ---------------------------------------------------------------------------
# compute_ais_diff — Ankur (no mismatches expected)
# ---------------------------------------------------------------------------

class TestAnkurDiff:
    def test_no_mismatches(self):
        report = compute_ais_diff(ANKUR_PROFILE)
        assert not report.has_mismatches


# ---------------------------------------------------------------------------
# TaxpayerProfile model validation
# ---------------------------------------------------------------------------

class TestTaxpayerProfile:
    def test_priya_basic_is_correct(self):
        assert PRIYA_PROFILE.form16.basic == 720_000

    def test_priya_metro(self):
        assert PRIYA_PROFILE.metro is True

    def test_priya_80c_total(self):
        assert PRIYA_PROFILE.declared.sec_80c.total == 150_000  # epf+elss

    def test_priya_ais_fd_interest(self):
        assert PRIYA_PROFILE.ais.fd_interest == 38_000

    def test_priya_declared_has_no_fd_interest(self):
        assert PRIYA_PROFILE.declared.fd_interest == 0


class TestSec80CTotal:
    def test_total_computed_correctly(self):
        s = Sec80C(epf=86_400, elss=63_600)
        assert s.total == 150_000

    def test_empty_total_is_zero(self):
        assert Sec80C().total == 0


# ---------------------------------------------------------------------------
# extractor_node — state contract (mocked LLM)
# ---------------------------------------------------------------------------

class TestExtractorNode:
    """Verify extractor_node writes the correct keys into state."""

    def test_success_state_keys(self):
        with patch("extractor.extractor.run_extractor") as mock_run:
            mock_run.return_value = (PRIYA_PROFILE, compute_ais_diff(PRIYA_PROFILE))
            result = extractor_node(
                {
                    "form16_text": "dummy",
                    "ais_text": "dummy",
                    "declarations_text": "dummy",
                }
            )
        assert result["extraction_status"] == "success"
        assert result["taxpayer_profile"] is PRIYA_PROFILE
        assert isinstance(result["mismatch_report"], AISMismatchReport)

    def test_failure_state_on_exception(self):
        with patch("extractor.extractor.run_extractor", side_effect=ValueError("oops")):
            result = extractor_node(
                {
                    "form16_text": "bad",
                    "ais_text": "bad",
                    "declarations_text": "bad",
                }
            )
        assert result["extraction_status"].startswith("failed")
        assert result["taxpayer_profile"] is None
        assert result["mismatch_report"] is None


# ---------------------------------------------------------------------------
# AISMismatchReport model
# ---------------------------------------------------------------------------

class TestAISMismatchReport:
    def test_empty_report_defaults(self):
        r = AISMismatchReport()
        assert r.has_mismatches is False
        assert r.total_undeclared_income == 0
        assert r.mismatches == []

    def test_mismatch_item_roundtrip(self):
        item = MismatchItem(
            income_type="fd_interest",
            ais_amount=38_000,
            declared_amount=0,
            difference=38_000,
            description="FD interest not declared",
        )
        assert item.difference == 38_000
