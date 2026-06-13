"""引用溯源核验。"""

from deep_research.verifier.checker import (
    FetchTools,
    ParallelKernel,
    Perspective,
    Verifier,
    aggregate_verdict,
    claim_terms_present,
    snippet_present,
    source_reachable,
)
from deep_research.verifier.models import (
    Citation,
    PerspectiveVerdict,
    Verdict,
    VerificationSummary,
)

__all__ = [
    "Citation",
    "FetchTools",
    "ParallelKernel",
    "Perspective",
    "PerspectiveVerdict",
    "Verdict",
    "VerificationSummary",
    "Verifier",
    "aggregate_verdict",
    "claim_terms_present",
    "snippet_present",
    "source_reachable",
]
