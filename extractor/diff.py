"""AIS vs taxpayer-declaration diff logic (P2).

Detects income appearing in AIS that the taxpayer has not declared,
which triggers HITL Gate 1 in the supervisor graph.
"""

from .models import TaxpayerProfile, AISMismatchReport, MismatchItem

_INCOME_CHECKS: list[tuple[str, str, str]] = [
    # (ais_field, declared_field, human_label)
    ("savings_interest", "savings_interest", "Savings account interest"),
    ("fd_interest",      "fd_interest",      "Fixed deposit interest"),
    ("dividend_income",  None,               "Dividend income"),
]


def compute_ais_diff(profile: TaxpayerProfile) -> AISMismatchReport:
    """Compare AIS income against taxpayer's declarations; return mismatch report."""
    mismatches: list[MismatchItem] = []

    for ais_field, declared_field, label in _INCOME_CHECKS:
        ais_amount: int = getattr(profile.ais, ais_field, 0)
        declared_amount: int = (
            getattr(profile.declared, declared_field, 0)
            if declared_field
            else 0
        )

        if ais_amount != declared_amount:
            diff = ais_amount - declared_amount
            if diff > 0:
                mismatches.append(
                    MismatchItem(
                        income_type=ais_field,
                        ais_amount=ais_amount,
                        declared_amount=declared_amount,
                        difference=diff,
                        description=(
                            f"{label}: AIS shows ₹{ais_amount:,} but taxpayer declared ₹{declared_amount:,}. "
                            f"Undeclared income of ₹{diff:,} will attract tax."
                        ),
                    )
                )

    total_undeclared = sum(m.difference for m in mismatches)
    return AISMismatchReport(
        mismatches=mismatches,
        total_undeclared_income=total_undeclared,
        has_mismatches=bool(mismatches),
    )
