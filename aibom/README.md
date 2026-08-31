# AI Bill of Materials: declaration format + drift detection

> A model, a prompt template, a policy version, and a firewall version are
> each free to change independently underneath a running AI system. If
> nothing declares what's *supposed* to be running, "drift" isn't a
> concept you can even state -- there's nothing to have drifted from.

This module defines the format for that declaration, and a drift-detection
query proving what's actually running matches it -- reapplying
[`completeness_proof/`](../completeness_proof/)'s central lesson (check
both directions against an authoritative source, don't just validate an
extract against itself) to a new kind of inventory.

## The format

[`schema/aibom_declaration.schema.json`](schema/aibom_declaration.schema.json)
-- a JSON Schema for one declared-component record: `system`,
`component_type` (one of `model` / `prompt` / `policy` / `firewall`),
`version`, `digest`, `effective_from`, `declared_by`. A full AI Bill of
Materials is a flat, append-only *list* of these records, not a single
"current state" object -- see [`schema/format.md`](schema/format.md) for
why that distinction is load-bearing, not stylistic.

[`examples/synthcorp_declared.json`](examples/synthcorp_declared.json) is
a synthetic worked example: two fabricated systems, `assistant-a` and
`assistant-b`, with a declaration history that includes a mid-stream
version bump (so the drift check has a real "as of when" question to
answer). It's schema-validated by
[`tests/test_drift_detection.py`](tests/test_drift_detection.py) before
it's ever used as input to anything else.

## The drift check

[`sql/drift_detection.sql`](sql/drift_detection.sql) compares declared
against observed in both directions, at the precise moment each
observation happened (an "as of" join against the declaration history --
comparing against only the *current* declaration would misjudge every
observation that happened mid-rollout). Four exception categories, all
seeded into [`data/aibom_fixtures.py`](data/aibom_fixtures.py) and found by exact
count and exact identity in the tests:

| Category | What it means |
|---|---|
| `VERSION_DRIFT` | A declaration existed at observation time; the running version doesn't match it. |
| `DIGEST_MISMATCH_SAME_VERSION_LABEL` | The version label matches, but the content digest doesn't -- a different build wearing the same tag. |
| `UNDECLARED_COMPONENT` | Something is running that was never declared for this system/component_type at all -- a shadow deployment. |
| `DECLARED_BUT_NEVER_OBSERVED` | A component is currently declared, but no observation of it exists at any version -- a coverage blind spot, the direction a purely per-observation check can't see. |

The synthetic scenario plants exactly one of each: `assistant-a`'s model
rollout catches up one observation late (self-resolving drift), its
policy gets redeployed under the same version label with different
content, `assistant-a`'s declared firewall is never confirmed by any
heartbeat, and `assistant-b` has a firewall running that was never
declared in the first place.

## Why there's a round-trip test

Same reasoning as
[`completeness_proof/README.md`](../completeness_proof/README.md#why-theres-a-round-trip-test):
a drift report returning zero exceptions looks identical whether the
system is genuinely clean or the query is silently broken.
[`tests/test_drift_detection.py`](tests/test_drift_detection.py) builds a
small dataset with zero drift, confirms the query agrees, then changes
one observed version and confirms the query names that exact instance,
system, component, and category -- not just "something's wrong."

## Running it

```
pip install -r ../requirements.txt
python3 -m pytest tests/ -v
```

Or from the repo root: `make test`.

`python3 data/aibom_fixtures.py` optionally regenerates `data/aibom_evidence.duckdb`
for manual inspection -- the tests build their own in-memory connection and
don't depend on that file existing.
