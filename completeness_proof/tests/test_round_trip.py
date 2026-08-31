"""
Tests for the completeness-proof queries.

Two things are being proven here, not just "the SQL runs":

1. The two-way reconciliation (02) actually finds every seeded defect class,
   by exact count -- not "finds something," but finds precisely what was
   planted, nothing more and nothing less.

2. The round-trip property that makes any of this trustworthy: a
   reconciliation that returns zero exceptions because everything genuinely
   ties has to be provably distinguishable from one that returns zero
   exceptions because the query itself is broken (wrong join column, empty
   table, a silently no-op WHERE clause). We prove it by starting from a
   dataset with zero exceptions, deliberately breaking it by dropping one
   record, and asserting the query notices. If a change to these queries
   ever makes that assertion fail, the query has regressed into the kind of
   silent-pass state this whole exercise exists to catch.
"""

import pathlib
import sys

import duckdb
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "data"))
import dataset  # noqa: E402

SQL_DIR = pathlib.Path(__file__).parent.parent / "sql"


def run_sql(con, filename: str):
    return con.sql((SQL_DIR / filename).read_text())


@pytest.fixture
def seeded_con():
    con = duckdb.connect()
    dataset.load_into(con)
    yield con
    con.close()


def test_dataset_generation_is_reproducible():
    a = dataset.build(seed=dataset.SEED)
    b = dataset.build(seed=dataset.SEED)
    assert a.idp_source == b.idp_source
    assert a.extract == b.extract


def test_two_way_reconciliation_finds_every_seeded_defect_by_exact_count(seeded_con):
    report = run_sql(seeded_con, "02_two_way_reconciliation.sql").fetchall()
    counts = {}
    for user_id, exception_type, detail in report:
        counts[exception_type] = counts.get(exception_type, 0) + 1

    assert counts.get("MISSING_FROM_EXTRACT") == dataset.N_MISSING
    assert counts.get("PHANTOM_IN_EXTRACT") == dataset.N_PHANTOM
    assert counts.get("DUPLICATE_KEY_IN_EXTRACT") == dataset.N_DUPLICATE
    assert counts.get("NULL_JOIN_KEY") == dataset.N_NULL_KEY
    assert counts.get("STATUS_DRIFT_STALE_ACTIVE") == dataset.N_STALE_ACTIVE
    assert counts.get("EMAIL_FORMAT_MISMATCH_NONBLOCKING") == dataset.N_EMAIL_MANGLED

    total_expected = (
        dataset.N_MISSING + dataset.N_PHANTOM + dataset.N_DUPLICATE
        + dataset.N_NULL_KEY + dataset.N_STALE_ACTIVE + dataset.N_EMAIL_MANGLED
    )
    assert len(report) == total_expected


def test_naive_reconciliation_reports_high_coverage_despite_real_defects(seeded_con):
    """
    Demonstrates the blind spot documented in 01_naive_reconciliation.sql:
    the naive query's headline number stays reassuringly high even though
    the two-way report (proven correct above) finds dozens of real defects,
    including active identities missing from the extract entirely.
    """
    naive_row = run_sql(seeded_con, "01_naive_reconciliation.sql").fetchone()
    _, _, reported_coverage_pct = naive_row

    two_way_report = run_sql(seeded_con, "02_two_way_reconciliation.sql").fetchall()
    missing_count = sum(1 for _, t, _ in two_way_report if t == "MISSING_FROM_EXTRACT")

    assert missing_count == dataset.N_MISSING
    assert missing_count > 0
    # The naive metric never looks at idp_source -> extract at all, so it
    # cannot reflect the missing rows in its own number -- that's the point.
    assert reported_coverage_pct > 99.0


def test_control_totals_checksum_matches_on_a_clean_dataset():
    """
    Builds a small hand-constructed dataset with zero defects: the extract
    is an exact, order-shuffled copy of the source's active population.
    Both sides of 03_control_totals.sql should report identical row counts,
    distinct key counts, and content checksums.
    """
    con = duckdb.connect()
    con.execute("""
        CREATE TABLE idp_source (user_id VARCHAR, email VARCHAR, department VARCHAR, status VARCHAR, revoked_at DATE)
    """)
    con.execute("""
        CREATE TABLE extract (user_id VARCHAR, email VARCHAR, department VARCHAR, status VARCHAR, extracted_at DATE)
    """)
    rows = [
        ("usr_1", "a.person@synthcorp.example", "engineering", "active", None),
        ("usr_2", "b.person@synthcorp.example", "finance", "active", None),
        ("usr_3", "c.person@synthcorp.example", "sales", "active", None),
    ]
    con.executemany("INSERT INTO idp_source VALUES (?, ?, ?, ?, ?)", rows)
    # Same identities, reversed order -- the checksum must be order-independent.
    for user_id, email, department, status, _ in reversed(rows):
        con.execute(
            "INSERT INTO extract VALUES (?, ?, ?, ?, ?)",
            (user_id, email, department, status, "2026-08-31"),
        )

    totals = run_sql(con, "03_control_totals.sql").fetchall()
    source_row = next(r for r in totals if r[0].startswith("idp_source"))
    extract_row = next(r for r in totals if r[0].startswith("extract"))

    assert source_row[1] == extract_row[1] == 3         # row_count
    assert source_row[2] == extract_row[2] == 3          # distinct_key_count
    assert source_row[3] == extract_row[3]                # content_checksum ties

    exceptions = run_sql(con, "02_two_way_reconciliation.sql").fetchall()
    assert exceptions == []

    con.close()


def test_round_trip_drop_is_surfaced_by_reconciliation_and_checksum():
    """
    The centerpiece assertion: start from a dataset proven clean above,
    deliberately drop one record from the extract, and prove both the
    exception report and the control-total checksum notice.

    This is what makes a "zero exceptions" result trustworthy instead of
    merely convenient -- it demonstrates the query can and does fail loudly
    when the data actually has a gap, rather than always reporting zero
    regardless of input.
    """
    con = duckdb.connect()
    con.execute("""
        CREATE TABLE idp_source (user_id VARCHAR, email VARCHAR, department VARCHAR, status VARCHAR, revoked_at DATE)
    """)
    con.execute("""
        CREATE TABLE extract (user_id VARCHAR, email VARCHAR, department VARCHAR, status VARCHAR, extracted_at DATE)
    """)
    rows = [
        ("usr_1", "a.person@synthcorp.example", "engineering", "active", None),
        ("usr_2", "b.person@synthcorp.example", "finance", "active", None),
        ("usr_3", "c.person@synthcorp.example", "sales", "active", None),
        ("usr_4", "d.person@synthcorp.example", "security", "active", None),
    ]
    con.executemany("INSERT INTO idp_source VALUES (?, ?, ?, ?, ?)", rows)

    # Drop usr_3 -- this is the deliberate, known gap the test proves gets caught.
    dropped_user_id = "usr_3"
    for user_id, email, department, status, _ in rows:
        if user_id == dropped_user_id:
            continue
        con.execute(
            "INSERT INTO extract VALUES (?, ?, ?, ?, ?)",
            (user_id, email, department, status, "2026-08-31"),
        )

    exceptions = run_sql(con, "02_two_way_reconciliation.sql").fetchall()
    assert len(exceptions) == 1
    user_id, exception_type, detail = exceptions[0]
    assert user_id == dropped_user_id
    assert exception_type == "MISSING_FROM_EXTRACT"

    totals = run_sql(con, "03_control_totals.sql").fetchall()
    source_checksum = next(r[3] for r in totals if r[0].startswith("idp_source"))
    extract_checksum = next(r[3] for r in totals if r[0].startswith("extract"))
    assert source_checksum != extract_checksum

    con.close()
