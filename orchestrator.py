"""P3: LangGraph supervisor and human approval gates.
Replace run_extractor and run_optimizer with other team members' implementations.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Literal, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class TaxState(TypedDict, total=False):
    taxpayer_id: str
    taxpayer_profile: dict[str, Any]
    mismatches: list[dict[str, Any]]
    income_confirmed: bool
    income_decisions: list[dict[str, Any]]
    regime_comparison: dict[str, Any]
    recommended_regime: str
    recommended_refund: float
    final_approval: bool
    final_decision: dict[str, Any]
    status: str
    filing_summary: dict[str, Any]


def run_extractor(state: TaxState) -> dict[str, Any]:
    """P2 integration point: expect profile with income_heads and mismatches."""
    profile = state.get("taxpayer_profile")
    if not profile:
        raise ValueError("Provide taxpayer_profile from P2's extractor.")
    return {
        "taxpayer_profile": profile,
        "mismatches": profile.get("mismatches", []),
        "status": "extracted",
    }


def gate1_confirm_income(state: TaxState) -> dict[str, Any]:
    mismatches = state.get("mismatches", [])
    if not mismatches:
        return {"income_confirmed": True, "income_decisions": [], "status": "income_verified"}

    answer = interrupt({
        "gate": 1,
        "title": "Confirm AIS income",
        "message": "Review each AIS mismatch and confirm whether it is real income.",
        "mismatches": mismatches,
        "expected_response": {
            "approved": True,
            "decisions": [{"id": "AIS-FD-001", "is_real_income": True}],
        },
    })
    if not isinstance(answer, dict):
        raise ValueError("Gate 1 expects a dictionary resume payload.")

    decisions = answer.get("decisions", [])
    if len(decisions) != len(mismatches):
        raise ValueError("Provide exactly one decision for every mismatch.")
    if any("is_real_income" not in d for d in decisions):
        raise ValueError("Each decision must include is_real_income.")

    accepted = answer.get("approved") is True and all(
        d["is_real_income"] is True for d in decisions
    )
    return {
        "income_confirmed": accepted,
        "income_decisions": decisions,
        "status": "income_verified" if accepted else "income_rejected",
    }


def run_optimizer(state: TaxState) -> dict[str, Any]:
    """P4 integration point: replace with deep agent + MCP tool calls."""
    if not state.get("income_confirmed"):
        raise ValueError("Gate 1 must be approved before optimization.")
    comparison = state.get("regime_comparison")
    if not comparison:
        raise ValueError("Connect P4's optimizer to provide regime_comparison.")
    regime = comparison.get("recommended_regime")
    if regime not in {"old", "new"}:
        raise ValueError("Optimizer must recommend 'old' or 'new'.")
    selected = comparison.get("regimes", {}).get(regime)
    if not isinstance(selected, dict) or "refund" not in selected:
        raise ValueError("Each regime must include a calculated refund/payable value.")
    return {
        "regime_comparison": comparison,
        "recommended_regime": regime,
        "recommended_refund": float(selected["refund"]),
        "status": "optimized",
    }


def gate2_approve_return(state: TaxState) -> dict[str, Any]:
    comparison = state["regime_comparison"]
    answer = interrupt({
        "gate": 2,
        "title": "Approve final tax result",
        "message": "Approve or reject the regime and computed refund/payable.",
        "comparison": comparison,
        "recommended_regime": state["recommended_regime"],
        "recommended_refund": state["recommended_refund"],
        "expected_response": {
            "approved": True,
            "regime": state["recommended_regime"],
            "refund": state["recommended_refund"],
        },
    })
    if not isinstance(answer, dict):
        raise ValueError("Gate 2 expects a dictionary resume payload.")

    if answer.get("approved") is not True:
        return {
            "final_approval": False,
            "final_decision": {"approved": False, "remarks": answer.get("remarks", "Rejected by taxpayer")},
            "status": "final_rejected",
        }

    regime = answer.get("regime")
    if regime not in {"old", "new"}:
        raise ValueError("Selected regime must be 'old' or 'new'.")
    selected = comparison.get("regimes", {}).get(regime)
    if not isinstance(selected, dict) or "refund" not in selected:
        raise ValueError(f"Optimizer has no refund/payable result for {regime} regime.")
    expected_refund = float(selected["refund"])
    supplied_refund = answer.get("refund")
    if supplied_refund is not None and abs(float(supplied_refund) - expected_refund) > 0.01:
        raise ValueError("Approved refund/payable differs from optimizer's calculated value.")

    decision = {"approved": True, "regime": regime, "refund": expected_refund}
    return {"final_approval": True, "final_decision": decision, "status": "approved"}


def write_filing_summary(state: TaxState) -> dict[str, Any]:
    if not state.get("income_confirmed") or not state.get("final_approval"):
        raise ValueError("Both human approval gates must pass before writing summary.")
    summary = {
        "taxpayer_id": state.get("taxpayer_id"),
        "income_heads": state.get("taxpayer_profile", {}).get("income_heads", {}),
        "income_decisions": state.get("income_decisions", []),
        "regime_comparison": state["regime_comparison"],
        "recommended_regime": state["recommended_regime"],
        "final_decision": state["final_decision"],
        "human_decisions": {"gate1_income_confirmed": True, "gate2_final_approved": True},
        "status": "approved_draft",
        "filed_with_government": False,
    }
    Path("filing_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return {"filing_summary": summary, "status": "completed"}


def route_after_gate1(state: TaxState) -> Literal["optimizer", "stop"]:
    return "optimizer" if state.get("income_confirmed") else "stop"


def route_after_gate2(state: TaxState) -> Literal["write_summary", "stop"]:
    return "write_summary" if state.get("final_approval") else "stop"


def stop_node(state: TaxState) -> dict[str, Any]:
    return {"status": state.get("status", "rejected")}


def build_graph():
    graph = StateGraph(TaxState)
    graph.add_node("extractor", run_extractor)
    graph.add_node("gate1", gate1_confirm_income)
    graph.add_node("optimizer", run_optimizer)
    graph.add_node("gate2", gate2_approve_return)
    graph.add_node("write_summary", write_filing_summary)
    graph.add_node("stop", stop_node)

    graph.add_edge(START, "extractor")
    graph.add_edge("extractor", "gate1")
    graph.add_conditional_edges("gate1", route_after_gate1, {"optimizer": "optimizer", "stop": "stop"})
    graph.add_edge("optimizer", "gate2")
    graph.add_conditional_edges("gate2", route_after_gate2, {"write_summary": "write_summary", "stop": "stop"})
    graph.add_edge("write_summary", END)
    graph.add_edge("stop", END)
    return graph.compile(checkpointer=InMemorySaver())


def main() -> None:
    app = build_graph()
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    # Demo input only. Replace the profile with P2's output and comparison
    # with P4's real MCP-backed results before the team demo.
    initial_state: TaxState = {
        "taxpayer_id": "PRIYA-001",
        "taxpayer_profile": {
            "income_heads": {"salary": 1_800_000, "savings_interest": 12_000, "fd_interest": 38_000},
            "mismatches": [{"id": "AIS-FD-001", "type": "FD interest", "amount": 38_000, "declared": False, "source": "AIS"}],
        },
        "regime_comparison": {
            "recommended_regime": "new",
            "regimes": {"old": {"refund": -41_995}, "new": {"refund": 33_800}},
        },
    }

    result = app.invoke(initial_state, config=config)
    while True:
        snapshot = app.get_state(config)
        if not snapshot.next:
            print(json.dumps(result, indent=2, ensure_ascii=False))
            break
        pending = [i for task in snapshot.tasks for i in task.interrupts]
        if not pending:
            raise RuntimeError(f"Graph paused unexpectedly at {snapshot.next}")
        request = pending[0].value
        print("\n" + json.dumps(request, indent=2, ensure_ascii=False))

        if request["gate"] == 1:
            choice = input("Confirm every listed mismatch as real income? (yes/no): ").strip().lower()
            decisions = [
                {"id": item["id"], "is_real_income": choice == "yes", "remarks": "Confirmed" if choice == "yes" else "Disputed by taxpayer"}
                for item in request["mismatches"]
            ]
            resume_value = {"approved": choice == "yes", "decisions": decisions}
        else:
            choice = input("Approve the recommended regime and refund/payable? (yes/no): ").strip().lower()
            resume_value = (
                {"approved": True, "regime": request["recommended_regime"], "refund": request["recommended_refund"]}
                if choice == "yes"
                else {"approved": False, "remarks": "Rejected by taxpayer"}
            )
        result = app.invoke(Command(resume=resume_value), config=config)


if __name__ == "__main__":
    main()
