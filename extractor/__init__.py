"""TaxPilot Document Extractor (P2) — public API."""

from .models import (
    AIS,
    AISMismatchReport,
    DeclaredByTaxpayer,
    Form16,
    MismatchItem,
    Sec80C,
    TaxpayerProfile,
)
from .diff import compute_ais_diff
from .extractor import create_extractor_chain, extractor_node, run_extractor
from .state import ExtractorState

__all__ = [
    # Models
    "AIS",
    "AISMismatchReport",
    "DeclaredByTaxpayer",
    "Form16",
    "MismatchItem",
    "Sec80C",
    "TaxpayerProfile",
    # Diff
    "compute_ais_diff",
    # Extractor
    "create_extractor_chain",
    "extractor_node",
    "run_extractor",
    # State
    "ExtractorState",
]
