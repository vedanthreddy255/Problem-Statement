"""Document Extractor chain (P2).

Uses LangChain ChatModel.with_structured_output(TaxpayerProfile) to turn
raw Form 16 / AIS / proof text into a typed TaxpayerProfile, then runs
the AIS diff to surface undeclared income before HITL Gate 1.
"""

from __future__ import annotations

import os
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.callbacks import BaseCallbackHandler

from .models import TaxpayerProfile, AISMismatchReport
from .diff import compute_ais_diff

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are an expert Indian tax document analyst for FY 2025-26 (AY 2026-27).

Your job is to extract a complete, accurate TaxpayerProfile from the three documents
provided: Form 16 (employer TDS certificate), AIS (Annual Information Statement from
the Income Tax Department), and the taxpayer's own declarations / investment proofs.

Rules:
- All monetary amounts are in Indian Rupees (INR). Strip commas, ₹ symbols, and spaces.
- "Metro" cities for HRA: Mumbai, Delhi, Kolkata, Chennai, Bengaluru, Hyderabad.
- Include ALL income sources found in the AIS, even if the taxpayer did NOT declare them.
  The AIS is the government's record and is authoritative.
- If a field is not mentioned, use 0 for integers and false for booleans.
- fy should be "2025-26".
"""

_HUMAN_TEMPLATE = """\
FORM 16:
{form16_text}

ANNUAL INFORMATION STATEMENT (AIS):
{ais_text}

TAXPAYER DECLARATIONS / INVESTMENT PROOFS:
{declarations_text}

Extract every field into the TaxpayerProfile structure.
"""

_PROMPT = ChatPromptTemplate.from_messages(
    [("system", _SYSTEM_PROMPT), ("human", _HUMAN_TEMPLATE)]
)


# ---------------------------------------------------------------------------
# Chain factory
# ---------------------------------------------------------------------------

def _default_llm() -> BaseChatModel:
    model = os.getenv("TAXPILOT_LLM_MODEL", "claude-sonnet-4-6")
    return ChatAnthropic(model=model, temperature=0)


def create_extractor_chain(
    llm: BaseChatModel | None = None,
    callbacks: list[BaseCallbackHandler] | None = None,
):
    """Return a runnable chain: dict → TaxpayerProfile."""
    _llm = llm or _default_llm()
    structured_llm = _llm.with_structured_output(TaxpayerProfile)
    chain = _PROMPT | structured_llm
    if callbacks:
        chain = chain.with_config({"callbacks": callbacks})
    return chain


# ---------------------------------------------------------------------------
# High-level helper
# ---------------------------------------------------------------------------

def run_extractor(
    form16_text: str,
    ais_text: str,
    declarations_text: str,
    llm: BaseChatModel | None = None,
    callbacks: list[BaseCallbackHandler] | None = None,
) -> tuple[TaxpayerProfile, AISMismatchReport]:
    """
    Extract TaxpayerProfile from raw document text, then compute AIS diff.

    Returns:
        (profile, mismatch_report)
    """
    chain = create_extractor_chain(llm=llm, callbacks=callbacks)
    profile: TaxpayerProfile = chain.invoke(
        {
            "form16_text": form16_text,
            "ais_text": ais_text,
            "declarations_text": declarations_text,
        }
    )
    mismatch_report = compute_ais_diff(profile)
    return profile, mismatch_report


# ---------------------------------------------------------------------------
# LangGraph node (P3 plugs this into the StateGraph)
# ---------------------------------------------------------------------------

def extractor_node(state: dict[str, Any]) -> dict[str, Any]:
    """
    LangGraph node for the Document Extractor step.

    Expects state keys:
      form16_text, ais_text, declarations_text
    Optionally:
      langfuse_callbacks — list of Langfuse callback handlers

    Writes state keys:
      taxpayer_profile, mismatch_report, extraction_status
    """
    callbacks = state.get("langfuse_callbacks", [])

    try:
        profile, mismatch_report = run_extractor(
            form16_text=state["form16_text"],
            ais_text=state["ais_text"],
            declarations_text=state["declarations_text"],
            callbacks=callbacks or None,
        )
        return {
            "taxpayer_profile": profile,
            "mismatch_report": mismatch_report,
            "extraction_status": "success",
        }
    except Exception as exc:
        return {
            "taxpayer_profile": None,
            "mismatch_report": None,
            "extraction_status": f"failed: {exc}",
        }
