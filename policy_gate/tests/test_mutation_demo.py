"""
Proves the "why exhaustive verification beats hand-picked test cases"
claim in ../README.md with actual passing/failing tests, not just an
assertion in prose.

../mutants/policy_evidence_off_by_one.rego is policy.rego with one
table cell's required evidence downgraded from "partial" to "none" (a
one-word change, documented in that file's header). It's a plausible
mistake: exactly the kind of edit a future contributor might make while
touching the requirement table for an unrelated reason.

Two things are checked:

1. The existing hand-picked suite (../rego/policy_test.rego), which
   reaches 100% line coverage of the real policy.rego, PASSES unchanged
   against the mutant. The bug is invisible to it -- coverage measures
   whether a line ran, not whether every input that touches it was
   tried.

2. The exhaustive sweep, run against the mutant instead of the real
   policy, FAILS -- and fails on exactly the two input combinations the
   one-word change actually affects (elevated risk, limited
   reversibility, evidence=none, confidence>=medium), which is precisely
   what the diff between the two table cells predicts.
"""

from __future__ import annotations

import itertools
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "reference"))
import reference  # noqa: E402

from opa_helpers import MUTANTS_DIR, OPA_AVAILABLE, REGO_DIR, eval_allow_autonomous, run_opa_test  # noqa: E402

POLICY_TEST = REGO_DIR / "policy_test.rego"
MUTANT = MUTANTS_DIR / "policy_evidence_off_by_one.rego"

pytestmark = pytest.mark.skipif(not OPA_AVAILABLE, reason="opa binary not found on PATH")


def test_hand_picked_suite_does_not_notice_the_mutant():
    result = run_opa_test(MUTANT, POLICY_TEST)
    assert result.returncode == 0, (
        "expected the hand-picked suite to pass against the mutant -- if it now "
        "fails, either the mutant or the hand-picked suite changed and this test's "
        "premise needs re-checking:\n" + result.stdout + result.stderr
    )


def test_exhaustive_sweep_catches_the_mutant_on_exactly_its_two_affected_inputs():
    mismatches = []
    for risk_flag, confidence, reversibility, approval_evidence in itertools.product(
        reference.RISK_FLAGS,
        reference.CONFIDENCE_TIERS,
        reference.REVERSIBILITY_LEVELS,
        reference.EVIDENCE_LEVELS,
    ):
        mutant_result = eval_allow_autonomous(MUTANT, risk_flag, confidence, reversibility, approval_evidence)
        reference_result = reference.allow_autonomous(risk_flag, confidence, reversibility, approval_evidence)
        if mutant_result != reference_result:
            mismatches.append((risk_flag, confidence, reversibility, approval_evidence))

    # The mutant loosens elevated/limited's evidence floor from "partial"
    # to "none". That changes the outcome only for inputs that were
    # relying on the evidence floor to deny -- i.e. evidence="none" with
    # confidence already at or above "medium" (confidence below "medium"
    # is still denied on confidence grounds either way).
    expected = {
        ("elevated", "medium", "limited", "none"),
        ("elevated", "high", "limited", "none"),
    }
    assert set(mismatches) == expected
