"""
Exhaustive input-space sweep for the autonomy gate.

This is the module's centerpiece proof, and it exists for a specific
reason: the hand-picked suite in ../rego/policy_test.rego reaches 100%
line coverage of ../rego/policy.rego (checked in test_coverage.py) --
and 100% line coverage is not the same claim as "every input produces
the intended output". A rule's body can execute on every test run while
still computing the wrong thing for inputs the suite never happened to
construct. See ../README.md and test_mutation_demo.py for a concrete
demonstration of exactly that gap.

The input space here is small and fully enumerable by construction: 4
fields x 3 values each = 81 combinations, no sampling, no fuzzing. Every
one of them is evaluated against the real Rego policy (via `opa eval`)
and checked against ../reference/reference.py, an independently-written
Python reimplementation of the same decision table. Agreement across all
81 is the actual claim; the exact allow/deny split (computed by hand in
the assertion below, not derived from either implementation) is the
check that neither implementation is trivially agreeing with itself by
both being broken the same way.
"""

from __future__ import annotations

import itertools
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "reference"))
import reference  # noqa: E402

from opa_helpers import OPA_AVAILABLE, REGO_DIR, eval_allow_autonomous  # noqa: E402

POLICY = REGO_DIR / "policy.rego"

pytestmark = pytest.mark.skipif(not OPA_AVAILABLE, reason="opa binary not found on PATH")


def all_combinations():
    return itertools.product(
        reference.RISK_FLAGS,
        reference.CONFIDENCE_TIERS,
        reference.REVERSIBILITY_LEVELS,
        reference.EVIDENCE_LEVELS,
    )


def test_input_space_size_is_81():
    # Sanity check on the sweep itself: if this ever drops (e.g. a typo
    # collapses one of the value lists), the "exhaustive" claim below is
    # silently no longer exhaustive.
    assert len(list(all_combinations())) == 81


def test_policy_agrees_with_reference_on_every_combination():
    mismatches = []
    allow_count = 0

    for risk_flag, confidence, reversibility, approval_evidence in all_combinations():
        rego_result = eval_allow_autonomous(POLICY, risk_flag, confidence, reversibility, approval_evidence)
        reference_result = reference.allow_autonomous(risk_flag, confidence, reversibility, approval_evidence)

        if rego_result != reference_result:
            mismatches.append(
                (risk_flag, confidence, reversibility, approval_evidence, rego_result, reference_result)
            )
        if rego_result:
            allow_count += 1

    assert mismatches == [], (
        f"{len(mismatches)} of 81 combinations disagree between policy.rego and "
        f"reference.py (risk_flag, confidence, reversibility, approval_evidence, "
        f"rego_result, reference_result): {mismatches}"
    )

    # Worked out by hand from the decision table, independently of both
    # implementations: for each of the 6 non-critical (risk_flag,
    # reversibility) cells, the count of (confidence, evidence) pairs
    # meeting that cell's requirement is (3 - min_confidence_rank) *
    # (3 - min_evidence_rank).
    #   none/reversible:        (3-0)*(3-0) = 9
    #   none/limited:            (3-0)*(3-1) = 6
    #   none/irreversible:       (3-1)*(3-2) = 2
    #   elevated/reversible:     (3-1)*(3-0) = 6
    #   elevated/limited:        (3-1)*(3-1) = 4
    #   elevated/irreversible:   (3-2)*(3-2) = 1
    # Sum = 28. critical contributes 0 (all 27 of its combinations deny).
    assert allow_count == 28
    total = len(list(all_combinations()))
    assert total - allow_count == 53
