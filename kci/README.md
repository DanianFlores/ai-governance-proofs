# KCI definition format

> A Key Control Indicator is only evidence if its definition is precise
> enough for two people to compute the same number from it -- and if every
> later change to that definition is recorded, not absorbed into the
> trend line.

This module is a reusable format for specifying a KCI, plus one fully
worked synthetic example that shows why the format's version-and-change-log
fields aren't paperwork.

## The format

[`format.md`](format.md) -- seven fields: indicator name & control
objective, population definition, versioned measurement logic, threshold,
evidence source, owner & escalation, change log. Each field closes a
specific way KCIs go soft in practice (an inferred population, an
undated logic change, a threshold nobody can explain, a metric nobody
actually owns).

## The worked example

[`examples/stale_access_kci.md`](examples/stale_access_kci.md) -- all
seven fields filled out for a **Stale Access Non-Removal Rate** indicator,
built directly on the `STATUS_DRIFT_STALE_ACTIVE` exception category
[`completeness_proof/`](../completeness_proof/) defines, extended across
two measurement snapshots instead of one. Every number in it is checked by
[`tests/test_delta_attribution.py`](tests/test_delta_attribution.py).

## Delta attribution: telling a logic change apart from a real change

The synthetic scenario: between snapshot A (2026-07-31) and snapshot B
(2026-08-31), two things happen at once -- the revoked population moves
(remediations happen, one new revocation hasn't propagated yet), *and* the
control owner adds a 2-day propagation grace period to the measurement
logic partway through (`logic_v1` -> `logic_v2`, see
[`sql/logic_v1_no_grace.sql`](sql/logic_v1_no_grace.sql) and
[`sql/logic_v2_grace_period.sql`](sql/logic_v2_grace_period.sql)). The
headline number swings from 60.0% to 16.7%. How much of that is the
control actually getting better, and how much is just a redefinition?

[`sql/delta_attribution.sql`](sql/delta_attribution.sql) decomposes the
swing into a population effect and a logic effect -- and computes that
decomposition two ways, because which effect you hold fixed while
measuring the other changes the split you get. Both orderings reconstruct
the same total exactly; they disagree with each other on the individual
population/logic split by a nonzero amount (the interaction between the
two effects). Reporting only one ordering, without saying which, lets
whoever's presenting the number pick whichever story they'd rather tell.
The file's header comment and
[`examples/stale_access_kci.md`](examples/stale_access_kci.md) walk
through why that matters; the test proves the interaction term is real
and not a rounding artifact.

## Why there's a test beyond "the SQL runs"

[`tests/test_delta_attribution.py`](tests/test_delta_attribution.py)
checks three things: that each logic version produces the exact
population/stale counts worked out by hand in the example doc; that the
delta-attribution bridge identity (population effect + logic effect =
total delta) holds exactly, verified independently in Python with exact
`Fraction` arithmetic rather than by trusting the SQL's own output against
itself; and that the interaction term between the two attribution
orderings is nonzero -- so a future edit that accidentally made the two
effects independent (and the "report both orderings" argument moot) would
fail a test instead of just quietly stop mattering.

## Running it

```
pip install -r ../requirements.txt
python3 -m pytest tests/ -v
```

Or from the repo root: `make test`.

`python3 data/fixtures.py` optionally regenerates `data/kci_evidence.duckdb`
for manual inspection with any SQL client -- the tests themselves build
their own in-memory connection and don't depend on that file existing.
