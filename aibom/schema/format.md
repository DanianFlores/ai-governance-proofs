# AI Bill of Materials: declaration format

An AI system's behavior is a function of four things changing
independently underneath it: the model, the prompt it's driven by, the
policy gate deciding what it's allowed to do (see
[`policy_gate/`](../../policy_gate/)), and the firewall filtering its
inputs and outputs. "What's running in production" is only evidence if
it's a specific, versioned claim someone is accountable for -- not a
description of whatever happens to be deployed.

[`aibom_declaration.schema.json`](aibom_declaration.schema.json) is the
format for that claim. Six fields, each closing a specific way a
component inventory goes soft:

- **`system` + `component_type`** -- scope. Drift detection is meaningless
  without knowing what's being compared against what; a policy version
  that's correct for one system is drift for another.
- **`version`** -- the human-readable claim.
- **`digest`** -- the claim a version label alone can't make. Two builds
  can be retagged with the same version string by mistake; only a content
  identifier catches that. See
  [`../sql/drift_detection.sql`](../sql/drift_detection.sql)'s
  `DIGEST_MISMATCH_SAME_VERSION_LABEL` category for what happens when this
  field is the only thing that disagrees.
- **`effective_from`** -- makes the format a changelog, not a snapshot.
  Comparing "what's running now" against "the current declaration" misses
  every case where an observation happened mid-rollout, before or after a
  declared cutover -- which is most of them, in any system that deploys
  gradually. Declaring a full history instead of a single current state is
  what lets drift detection ask "what *should* have been running at the
  moment this was observed," not just "what's supposed to be running
  right now."
- **`declared_by`** -- accountability. A version nobody signed off on is
  configuration, not evidence.

## Why a list of declarations, not a single document

A tempting simpler format is one JSON object per system: `{"model": "v2",
"prompt": "v5", ...}`, overwritten whenever something changes. That
format can only ever answer "what's declared right now" -- it has already
discarded the history needed to check anything observed before the last
edit. [`../examples/synthcorp_declared.json`](../examples/synthcorp_declared.json)
is a flat, append-only list of declarations instead, exactly because the
drift check in [`../sql/drift_detection.sql`](../sql/drift_detection.sql)
needs to reconstruct "what was declared as of this specific timestamp,"
not just read the latest value.

## Validating the example

[`../tests/test_drift_detection.py`](../tests/test_drift_detection.py)
validates every record in `synthcorp_declared.json` against this schema
with the `jsonschema` library before it's ever loaded into the drift
check -- so a malformed synthetic example (missing field, wrong
`component_type`, a `digest` without the `sha256:` prefix) fails loudly at
the schema level instead of silently producing a wrong drift report
downstream.
