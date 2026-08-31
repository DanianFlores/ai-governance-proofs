"""
Independent reference implementation of the autonomy-gate decision table
in ../rego/policy.rego.

Deliberately written as a plain if/elif ladder instead of mirroring the
Rego version's rank-table-and-lookup structure, so that a mistake in one
implementation has to independently reproduce itself in a structurally
different implementation to survive
../tests/test_exhaustive_sweep.py's full 81-combination comparison. This
file is not policy -- it exists only to be an oracle the Rego gets
checked against, and is not itself covered by policy_test.rego.
"""

from __future__ import annotations

CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}
EVIDENCE_RANK = {"none": 0, "partial": 1, "full": 2}

RISK_FLAGS = ("none", "elevated", "critical")
CONFIDENCE_TIERS = ("low", "medium", "high")
REVERSIBILITY_LEVELS = ("reversible", "limited", "irreversible")
EVIDENCE_LEVELS = ("none", "partial", "full")


def allow_autonomous(risk_flag: str, confidence: str, reversibility: str, approval_evidence: str) -> bool:
    if risk_flag == "critical":
        return False

    if risk_flag == "none":
        if reversibility == "reversible":
            min_confidence, min_evidence = "low", "none"
        elif reversibility == "limited":
            min_confidence, min_evidence = "low", "partial"
        elif reversibility == "irreversible":
            min_confidence, min_evidence = "medium", "full"
        else:
            raise ValueError(f"unknown reversibility: {reversibility!r}")
    elif risk_flag == "elevated":
        if reversibility == "reversible":
            min_confidence, min_evidence = "medium", "none"
        elif reversibility == "limited":
            min_confidence, min_evidence = "medium", "partial"
        elif reversibility == "irreversible":
            min_confidence, min_evidence = "high", "full"
        else:
            raise ValueError(f"unknown reversibility: {reversibility!r}")
    else:
        raise ValueError(f"unknown risk_flag: {risk_flag!r}")

    return (
        CONFIDENCE_RANK[confidence] >= CONFIDENCE_RANK[min_confidence]
        and EVIDENCE_RANK[approval_evidence] >= EVIDENCE_RANK[min_evidence]
    )
