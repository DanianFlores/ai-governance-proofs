# Autonomy gate: decides whether an AI system's proposed automated action
# may proceed without a human, or must be routed to human review first.
#
# This is a generic decision table, not a reproduction of any specific
# production policy. It exists to demonstrate the shape a policy gate
# takes when it has to be provable, not just plausible: an explicit,
# reviewable table plus a comparison rule, small enough that its entire
# input space can be enumerated and checked -- see
# ../tests/test_exhaustive_sweep.py.
#
# Inputs (all required):
#   input.risk_flag         "none" | "elevated" | "critical"
#   input.confidence         "low" | "medium" | "high"
#   input.reversibility       "reversible" | "limited" | "irreversible"
#   input.approval_evidence   "none" | "partial" | "full"
#
# Output:
#   allow_autonomous  true  -> the action may proceed without a human
#                     false -> the action requires human review first

package autonomy_gate

import rego.v1

# Ordinal ranks for "at least this level" comparisons. Rego has no
# built-in ordering for strings -- without an explicit rank table, a
# comparison like `input.confidence >= "medium"` would silently compare
# strings lexically ("high" < "low" < "medium"), which is wrong and would
# not raise an error. Making the ranking explicit is what lets the
# comparisons below be trusted.
confidence_rank := {"low": 0, "medium": 1, "high": 2}

evidence_rank := {"none": 0, "partial": 1, "full": 2}

# The decision table: minimum confidence tier and minimum accumulated
# approval evidence required to proceed autonomously, indexed by
# [risk_flag][reversibility]. "critical" is deliberately not a key here --
# it is handled as an unconditional block below, not as one more row to
# weigh against the others. A risk-flagged-critical action does not get to
# out-argue that flag with enough confidence or evidence; that is a
# property of the gate's design, not an accident of the table's shape.
requirement := {
	"none": {
		"reversible": {"confidence": "low", "evidence": "none"},
		"limited": {"confidence": "low", "evidence": "partial"},
		"irreversible": {"confidence": "medium", "evidence": "full"},
	},
	"elevated": {
		"reversible": {"confidence": "medium", "evidence": "none"},
		"limited": {"confidence": "medium", "evidence": "partial"},
		"irreversible": {"confidence": "high", "evidence": "full"},
	},
}

default allow_autonomous := false

# Critical risk always requires human review. No confidence level and no
# amount of accumulated approval evidence overrides this -- it is a floor
# on the decision, not an input the other three factors can outweigh.
allow_autonomous := false if input.risk_flag == "critical"

# Below critical, the action may proceed autonomously once both the
# confidence tier and the accumulated approval evidence meet or exceed
# this risk_flag / reversibility combination's requirement.
allow_autonomous := true if {
	input.risk_flag != "critical"
	req := requirement[input.risk_flag][input.reversibility]
	confidence_rank[input.confidence] >= confidence_rank[req.confidence]
	evidence_rank[input.approval_evidence] >= evidence_rank[req.evidence]
}
