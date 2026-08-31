"""
Confirms the "100% branch coverage" claim about ../rego/policy_test.rego
by actually running `opa test --coverage` and checking the reported
number, rather than that claim being a one-time manual check that can
silently go stale as the policy changes.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from opa_helpers import OPA_AVAILABLE, REGO_DIR

pytestmark = pytest.mark.skipif(not OPA_AVAILABLE, reason="opa binary not found on PATH")

POLICY = REGO_DIR / "policy.rego"
POLICY_TEST = REGO_DIR / "policy_test.rego"


def test_policy_test_suite_passes():
    result = subprocess.run(
        ["opa", "test", str(POLICY), str(POLICY_TEST)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_policy_test_suite_reaches_100_percent_coverage_of_policy_rego():
    result = subprocess.run(
        ["opa", "test", str(POLICY), str(POLICY_TEST), "--coverage", "--format=json"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    report = json.loads(result.stdout)
    policy_coverage = report["files"][str(POLICY)]
    assert policy_coverage["coverage"] == 100
    assert policy_coverage.get("not_covered", []) == []
