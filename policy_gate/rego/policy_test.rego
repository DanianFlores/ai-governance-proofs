# Hand-picked unit tests for policy.rego: one "meets the requirement"
# case and one "falls one level short" case for each of the six
# (risk_flag, reversibility) table cells that aren't the critical-risk
# override, plus two cases proving the override itself. This suite is
# small enough to review in a couple of minutes and is designed to reach
# 100% line coverage of policy.rego (checked by
# ../tests/test_coverage.py) -- see ../README.md's "why exhaustive beats
# hand-picked" section, and ../tests/test_mutation_demo.py, for what a
# suite like this one still misses despite full coverage.

package autonomy_gate

import rego.v1

# --- none / reversible: requires confidence>=low, evidence>=none -------
# Every value satisfies "at least low" and "at least none" -- there is no
# way to fall short of this cell's requirement, so it gets one test.

test_none_reversible_always_allowed if {
	allow_autonomous with input as {
		"risk_flag": "none",
		"confidence": "low",
		"reversibility": "reversible",
		"approval_evidence": "none",
	}
}

# --- none / limited: requires confidence>=low, evidence>=partial -------

test_none_limited_meets_requirement if {
	allow_autonomous with input as {
		"risk_flag": "none",
		"confidence": "low",
		"reversibility": "limited",
		"approval_evidence": "partial",
	}
}

test_none_limited_insufficient_evidence if {
	not allow_autonomous with input as {
		"risk_flag": "none",
		"confidence": "low",
		"reversibility": "limited",
		"approval_evidence": "none",
	}
}

# --- none / irreversible: requires confidence>=medium, evidence>=full --

test_none_irreversible_meets_requirement if {
	allow_autonomous with input as {
		"risk_flag": "none",
		"confidence": "medium",
		"reversibility": "irreversible",
		"approval_evidence": "full",
	}
}

test_none_irreversible_insufficient_evidence if {
	not allow_autonomous with input as {
		"risk_flag": "none",
		"confidence": "medium",
		"reversibility": "irreversible",
		"approval_evidence": "partial",
	}
}

# --- elevated / reversible: requires confidence>=medium, evidence>=none

test_elevated_reversible_meets_requirement if {
	allow_autonomous with input as {
		"risk_flag": "elevated",
		"confidence": "medium",
		"reversibility": "reversible",
		"approval_evidence": "none",
	}
}

test_elevated_reversible_insufficient_confidence if {
	not allow_autonomous with input as {
		"risk_flag": "elevated",
		"confidence": "low",
		"reversibility": "reversible",
		"approval_evidence": "none",
	}
}

# --- elevated / limited: requires confidence>=medium, evidence>=partial

test_elevated_limited_meets_requirement if {
	allow_autonomous with input as {
		"risk_flag": "elevated",
		"confidence": "medium",
		"reversibility": "limited",
		"approval_evidence": "partial",
	}
}

test_elevated_limited_insufficient_confidence if {
	not allow_autonomous with input as {
		"risk_flag": "elevated",
		"confidence": "low",
		"reversibility": "limited",
		"approval_evidence": "partial",
	}
}

# --- elevated / irreversible: requires confidence>=high, evidence>=full

test_elevated_irreversible_meets_requirement if {
	allow_autonomous with input as {
		"risk_flag": "elevated",
		"confidence": "high",
		"reversibility": "irreversible",
		"approval_evidence": "full",
	}
}

test_elevated_irreversible_insufficient_confidence if {
	not allow_autonomous with input as {
		"risk_flag": "elevated",
		"confidence": "medium",
		"reversibility": "irreversible",
		"approval_evidence": "full",
	}
}

# --- critical: overrides everything, regardless of how favorable the
#     other three inputs are ------------------------------------------

test_critical_blocks_even_with_maximal_confidence_and_evidence if {
	not allow_autonomous with input as {
		"risk_flag": "critical",
		"confidence": "high",
		"reversibility": "reversible",
		"approval_evidence": "full",
	}
}

test_critical_blocks_with_minimal_everything if {
	not allow_autonomous with input as {
		"risk_flag": "critical",
		"confidence": "low",
		"reversibility": "irreversible",
		"approval_evidence": "none",
	}
}
