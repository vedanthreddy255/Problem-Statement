import json
import os
import sys
import uuid

from langfuse import get_client, propagate_attributes
from langfuse.langchain import CallbackHandler
from langgraph.types import Command

from graph import build_graph  # P3's compiled StateGraph (with MemorySaver)

os.environ["LANGFUSE_PUBLIC_KEY"] = 
os.environ["LANGFUSE_SECRET_KEY"] = 
os.environ["LANGFUSE_BASE_URL"] = 

langfuse = get_client()

AGENT_TAGS = ["taxpilot", "agent:extractor", "agent:hitl_gate_1", "agent:regime_optimizer", "agent:hitl_gate_2"]

VISWA = {
    "id": "VISWA-sharma",
    "name": "VISWA Sharma",
    "documents": {
        "form16": {"employer": "Acme Software Pvt Ltd", "gross_salary": 1800000, "basic": 720000,
                   "hra_received": 288000, "professional_tax": 2400, "tds_deducted": 195000},
        "ais": {"salary": 1800000, "savings_interest": 12000, "fd_interest": 38000, "tds_total": 195000},
        "declared_by_taxpayer": {"rent_paid_annual": 300000, "rent_receipts_available": True,
                                 "sec_80c": {"epf": 86400, "elss": 63600}, "sec_80d_self": 25000,
                                 "savings_interest": 12000},
    },
}

EXPECTED = {
    "old": {"hra_exempt": 228000, "gross_total_income": 1569600, "deductions": 185000,
            "taxable_income": 1384600, "total_tax": 236995, "tds_paid": 195000, "refund": -41995},
    "new": {"gross_total_income": 1775000, "taxable_income": 1775000,
            "total_tax": 161200, "tds_paid": 195000, "refund": 33800},
    "recommendation": "new",
    "savings": 75795,
    "refund": 33800,
}


def trace_link(trace_id):
    try:
        return langfuse.get_trace_url(trace_id=trace_id)
    except Exception:
        return f"trace_id={trace_id} (open it in the Langfuse UI)"


def agent_config(session_id, agent):
    """Teammates call this for any sub-run (chain, deep agent, MCP agent) so it lands in the same trace."""
    return {
        "callbacks": [CallbackHandler()],
        "tags": [f"agent:{agent}"],
        "metadata": {"langfuse_session_id": session_id, "langfuse_tags": [f"agent:{agent}"]},
    }


def is_approved(decision):
    if isinstance(decision, dict):
        return bool(decision.get("approved", False))
    if isinstance(decision, str):
        return decision.strip().lower().startswith(("y", "approve", "confirm", "true"))
    return bool(decision)


def run_taxpilot(graph, taxpayer, decide, session_id=None):
    """Runs the full graph as ONE Langfuse trace, handles both HITL gates and scores each decision."""
    session_id = session_id or f"taxpilot-{taxpayer['id']}-{uuid.uuid4().hex[:6]}"
    decisions = []
    if os.path.exists("filing_summary.json"):
        os.remove("filing_summary.json")  # avoid reading a stale file from a previous run

    with langfuse.start_as_current_observation(
        as_type="span", name=f"taxpilot-{taxpayer['id']}", input=taxpayer["documents"]
    ) as root, propagate_attributes(user_id=taxpayer["id"], session_id=session_id, tags=AGENT_TAGS):
        trace_id = langfuse.get_current_trace_id()

        config = agent_config(session_id, "supervisor")
        config["configurable"] = {"thread_id": session_id}

        result = graph.invoke({"taxpayer_id": taxpayer["id"], "documents": taxpayer["documents"]}, config)

        gate = 0
        while result.get("__interrupt__"):
            gate += 1
            payload = result["__interrupt__"][0].value
            decision = decide(gate, payload)
            approved = is_approved(decision)
            decisions.append({"gate": gate, "approved": approved, "payload": payload, "decision": decision})

            langfuse.create_score(trace_id=trace_id, name=f"hitl_gate_{gate}_approved",
                                  value=float(approved), data_type="BOOLEAN",
                                  comment=json.dumps(decision, default=str))
            result = graph.invoke(Command(resume=decision), config)

        if decisions:
            rate = sum(d["approved"] for d in decisions) / len(decisions)
            langfuse.create_score(trace_id=trace_id, name="hitl_approval_rate", value=rate, data_type="NUMERIC")

        root.update(output={"gates": gate, "approved": [d["approved"] for d in decisions]})

    return {"result": result, "decisions": decisions, "trace_id": trace_id, "session_id": session_id}


def load_summary(result):
    if isinstance(result, dict) and result.get("filing_summary"):
        return result["filing_summary"]
    with open("filing_summary.json") as f:
        return json.load(f)


def check_against_expected(summary):
    """Returns a list of mismatches (empty list = pass). Tolerance: 1 rupee."""
    errors = []
    for regime in ("old", "new"):
        for field, want in EXPECTED[regime].items():
            got = summary.get("regimes", {}).get(regime, {}).get(field)
            if got is None or abs(got - want) > 1:
                errors.append(f"{regime}.{field}: expected {want}, got {got}")
    if EXPECTED["recommendation"] not in str(summary.get("recommendation", "")).lower():
        errors.append(f"recommendation: expected {EXPECTED['recommendation']}, got {summary.get('recommendation')}")
    for field in ("savings", "refund"):
        got = summary.get(field)
        if got is None or abs(got - EXPECTED[field]) > 1:
            errors.append(f"{field}: expected {EXPECTED[field]}, got {got}")
    if not summary.get("human_decisions"):
        errors.append("human_decisions missing in filing_summary.json")
    return errors


def scripted(*answers):
    return lambda gate, payload: answers[gate - 1] if gate <= len(answers) else {"approved": True}


def manual(gate, payload):
    print(f"\n--- HITL gate {gate} ---\n{json.dumps(payload, indent=2, default=str)}")
    return {"approved": input("Approve? (y/n): ").strip().lower().startswith("y")}


def test_main_case(graph):
    run = run_taxpilot(graph, VISWA, scripted({"approved": True}, {"approved": True}))
    try:
        errors = check_against_expected(load_summary(run["result"]))
    except FileNotFoundError:
        errors = ["no filing_summary in final state and no filing_summary.json written"]

    gate1_text = json.dumps(run["decisions"][0]["payload"], default=str).replace(",", "") if run["decisions"] else ""
    if "38000" not in gate1_text:
        errors.append("gate 1 did not flag the 38,000 FD interest")
    if len(run["decisions"]) != 2:
        errors.append(f"expected 2 HITL gates, got {len(run['decisions'])}")

    langfuse.create_score(trace_id=run["trace_id"], name="expected_table_match",
                          value=float(not errors), data_type="BOOLEAN", comment="; ".join(errors) or "all match")
    return errors, run


def test_rejection_path(graph):
    run = run_taxpilot(graph, VISWA, scripted({"approved": False, "reason": "FD is not mine"}, {"approved": True}))
    errors = []
    if not run["decisions"] or run["decisions"][0]["approved"]:
        errors.append("rejection at gate 1 was not recorded")
    try:
        if load_summary(run["result"]).get("refund") == EXPECTED["refund"]:
            errors.append("refund unchanged after rejecting the FD interest")
    except FileNotFoundError:
        pass  # graph may legitimately stop without a filing summary on rejection
    langfuse.create_score(trace_id=run["trace_id"], name="rejection_path_ok",
                          value=float(not errors), data_type="BOOLEAN", comment="; ".join(errors) or "ok")
    return errors, run


if __name__ == "__main__":
    graph = build_graph()

    if "--manual" in sys.argv:
        run = run_taxpilot(graph, VISWA, manual)
        print("Trace:", trace_link(run["trace_id"]))
    else:
        for test in (test_main_case, test_rejection_path):
            errs, run = test(graph)
            print(f"{test.__name__}: {'PASS' if not errs else 'FAIL'}")
            for e in errs:
                print("  -", e)
            print("  trace:", trace_link(run["trace_id"]))

    langfuse.flush()
