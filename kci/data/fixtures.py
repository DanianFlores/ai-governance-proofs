"""
Synthetic two-snapshot dataset for the Stale Access Non-Removal Rate KCI.

Everything here is fabricated, hand-authored (not randomly generated) --
unlike completeness_proof/data/dataset.py, this module needs identities
revoked at specific, deliberately chosen dates relative to two measurement
snapshots, so the grace-period logic difference in
sql/logic_v2_grace_period.sql has something real to bite on. Hand-authoring
eight rows keeps every number in this module checkable by eye; see
examples/stale_access_kci.md for the walk-through.

Same schema conventions as completeness_proof/ (user_id keys, a
revoked_at authority field, an 'active' status meaning "downstream extract
currently believes this identity has access") so the two modules read as
one system, not two unrelated demos -- this KCI is built directly on the
STATUS_DRIFT_STALE_ACTIVE exception category that
completeness_proof/sql/02_two_way_reconciliation.sql defines.

Three tables:

  identities            -- the authoritative revocation record. NULL
                            revoked_at means still active.

  extract_observations  -- one row per (user_id, period) *only* where the
                            downstream extract showed that identity as
                            status='active' at that snapshot. Absence is
                            not silence: for a user_id already revoked as
                            of that period, absence means the extract
                            correctly shows no access. Presence for an
                            already-revoked identity is exactly the defect
                            this KCI counts.

  snapshot_periods       -- the two measurement dates this module compares.
"""

from __future__ import annotations

# user_id, revoked_at (None = still active as of both snapshots)
IDENTITIES = [
    ("usr_01", "2026-06-01"),  # revoked well before period A; clean by both periods
    ("usr_02", "2026-06-15"),  # revoked before A; stale at A, remediated by B
    ("usr_03", "2026-07-30"),  # revoked 1 day before A's snapshot -- inside A's grace window
    ("usr_04", "2026-08-30"),  # revoked 1 day before B's snapshot -- inside B's grace window
    ("usr_05", "2026-08-10"),  # revoked after A (not yet in A's population); clean by B
    ("usr_06", "2026-07-01"),  # revoked before A; clean by both periods
    ("usr_07", "2026-05-01"),  # revoked long before A; stale at A AND still stale at B
    ("usr_08", None),           # never revoked -- irrelevant to this KCI, included for realism
]

# (user_id, period) pairs where the downstream extract shows status='active'
# for an identity idp_source has already revoked as of that period's
# snapshot date -- i.e. the stale-access defect this KCI measures.
STALE_OBSERVATIONS = [
    ("usr_02", "A"),
    ("usr_03", "A"),
    ("usr_07", "A"),
    ("usr_04", "B"),
    ("usr_07", "B"),
]

SNAPSHOT_PERIODS = [
    ("A", "2026-07-31"),
    ("B", "2026-08-31"),
]


def load_into(con) -> None:
    """Create identities, extract_observations, and snapshot_periods in the given DuckDB connection."""
    con.execute("CREATE OR REPLACE TABLE identities (user_id VARCHAR, revoked_at DATE)")
    con.execute(
        "CREATE OR REPLACE TABLE extract_observations (user_id VARCHAR, period VARCHAR, status VARCHAR)"
    )
    con.execute("CREATE OR REPLACE TABLE snapshot_periods (period VARCHAR, snapshot_date DATE)")

    con.executemany("INSERT INTO identities VALUES (?, ?)", IDENTITIES)
    con.executemany(
        "INSERT INTO extract_observations VALUES (?, ?, 'active')",
        STALE_OBSERVATIONS,
    )
    con.executemany("INSERT INTO snapshot_periods VALUES (?, ?)", SNAPSHOT_PERIODS)


if __name__ == "__main__":
    import pathlib
    import duckdb

    here = pathlib.Path(__file__).parent
    db_path = here / "kci_evidence.duckdb"
    db_path.unlink(missing_ok=True)

    con = duckdb.connect(str(db_path))
    load_into(con)
    con.close()

    print(f"built {db_path.name}: {len(IDENTITIES)} identities, {len(STALE_OBSERVATIONS)} stale observations")
