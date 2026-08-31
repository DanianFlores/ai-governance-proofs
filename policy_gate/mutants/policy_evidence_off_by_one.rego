# DELIBERATELY WRONG. This is not the real gate -- do not deploy it.
#
# A copy of ../rego/policy.rego with exactly one change: the
# elevated/limited table cell's required evidence is "none" here instead
# of the correct "partial". That's the entire bug -- a one-word edit.
#
# It exists to demonstrate, with an actual passing/failing test rather
# than an assertion in prose, why a hand-picked test suite that reaches
# 100% line coverage still isn't the same thing as proof: see
# ../tests/test_mutation_demo.py, which runs ../rego/policy_test.rego
# against this file (it passes -- the bug is invisible to that suite) and
# then runs the exhaustive sweep against it (it fails, on exactly the two
# input combinations this change affects). See ../README.md for the full
# argument.

package autonomy_gate

import rego.v1

confidence_rank := {"low": 0, "medium": 1, "high": 2}

evidence_rank := {"none": 0, "partial": 1, "full": 2}

requirement := {
	"none": {
		"reversible": {"confidence": "low", "evidence": "none"},
		"limited": {"confidence": "low", "evidence": "partial"},
		"irreversible": {"confidence": "medium", "evidence": "full"},
	},
	"elevated": {
		"reversible": {"confidence": "medium", "evidence": "none"},
		"limited": {"confidence": "medium", "evidence": "none"}, # BUG: should be "partial"
		"irreversible": {"confidence": "high", "evidence": "full"},
	},
}

default allow_autonomous := false

allow_autonomous := false if input.risk_flag == "critical"

allow_autonomous := true if {
	input.risk_flag != "critical"
	req := requirement[input.risk_flag][input.reversibility]
	confidence_rank[input.confidence] >= confidence_rank[req.confidence]
	evidence_rank[input.approval_evidence] >= evidence_rank[req.evidence]
}
