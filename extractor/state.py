"""Shared LangGraph TaxState definition — P2's contribution.

P3 (Orchestrator) imports this TypedDict and extends it with the full graph state.
All fields that the Document Extractor (P2) writes are defined here so every
node has a consistent, typed contract.
"""

from __future__ import annotations

from typing import Any, Optional, TypedDict

from .models import AISMismatchReport, TaxpayerProfile


class ExtractorState(TypedDict, total=False):
    # Input documents (set by the caller / CLI before the graph runs)
    form16_text: str
    ais_text: str
    declarations_text: str

    # Langfuse callback handlers injected by P5 before graph execution
    langfuse_callbacks: list[Any]

    # Outputs written by extractor_node
    taxpayer_profile: Optional[TaxpayerProfile]
    mismatch_report: Optional[AISMismatchReport]
    extraction_status: str   # "success" | "failed: <reason>"

    # Written by HITL Gate 1 (P3) after taxpayer confirms mismatches
    confirmed_mismatches: list[str]   # income_type keys taxpayer accepted
    rejected_mismatches: list[str]    # income_type keys taxpayer disputed
