# Completeness proof

> A control metric reporting "99.2% coverage" is meaningless unless you can
> prove the denominator is complete. An extract cannot validate itself.

This module is a worked example, on synthetic data, of what it actually
takes to prove an extract is complete relative to its source of truth --
not just check that the rows it happens to contain look fine.

## The scenario

- `idp_source` -- a synthetic identity provider's full user roster: 1,150
  identities, 1,000 currently active, 150 revoked. This is the authority.
  It defines what "complete" means.
- `extract` -- a synthetic access-certification extract that claims to
  contain every currently-active identity from `idp_source`. It doesn't,
  on purpose. Six defect classes are seeded in by
  [`data/dataset.py`](data/dataset.py) from a fixed random seed:

  | Defect | Count | What it looks like |
  |---|---|---|
  | Missing rows | 24 | Active identities absent from the extract entirely |
  | Phantom rows | 5 | Extract rows with no matching identity in the source |
  | Duplicate keys | 8 | Same `user_id` inserted twice into the extract |
  | NULL join key | 1 | An extract row with `user_id = NULL` |
  | Email format drift | 40 | Case/whitespace differences, no content change |
  | Stale status | 12 | Extract says `active`; source has since revoked them |

Run `python3 data/dataset.py` and it rebuilds `evidence.duckdb` (plus CSV
exports) byte-identically every time, from `SEED = 42` in `dataset.py`.

## The three queries

1. **[`sql/01_naive_reconciliation.sql`](sql/01_naive_reconciliation.sql)**
   -- the one-directional query most people write: "how much of the extract
   matches the source?" It reports coverage in the high 90s. It is wrong,
   and the comments in the file walk through exactly which defect classes
   it cannot see and why.

2. **[`sql/02_two_way_reconciliation.sql`](sql/02_two_way_reconciliation.sql)**
   -- defines the population explicitly from the source, checks both
   directions, and emits a labeled exception report: one row per defect,
   tagged with which of the six categories it is.

3. **[`sql/03_control_totals.sql`](sql/03_control_totals.sql)** -- a cheap
   tripwire: row count, distinct key count, and an order-independent
   content checksum (`SUM(HASH(...))`, commutative so row order never
   matters) for both sides. Fast enough to run on every pipeline execution
   as a "did anything change" signal before pulling the full report.

## Why there's a round-trip test

A reconciliation query that always returns zero exceptions looks, from the
outside, identical whether that's because the data is genuinely clean or
because the query is silently broken -- a wrong join column, an empty
table, a `WHERE` clause that never evaluates true.

[`tests/test_round_trip.py`](tests/test_round_trip.py) proves the
difference: it builds a small dataset with zero defects, confirms the
reconciliation and checksum both agree on that, then deliberately drops one
record and asserts the exception report names exactly that record and the
checksums diverge. A "zero exceptions" result only means something once
you've shown the query fails loudly on a known gap.

The same test file also asserts the two-way report finds every one of the
six seeded defects in `evidence.duckdb` by exact count, and that the naive
query's coverage number stays reassuringly high despite them -- so the
"what it misses" claim in `01_naive_reconciliation.sql` isn't just asserted
in a comment, it's checked.

## Running it

```
pip install -r ../requirements.txt
python3 data/dataset.py        # optional: regenerates evidence.duckdb + CSVs
python3 -m pytest tests/ -v
```

Or from the repo root: `make test`.
