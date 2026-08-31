"""
Tests for the AI Bill of Materials schema and drift-detection query.

Three things are being proven:

1. The synthetic example (../examples/synthcorp_declared.json) actually
   validates against the published schema -- so schema/format.md's
   description of the format and the example it points to can't quietly
   drift apart.

2. The drift-detection query (../sql/drift_detection.sql) finds every
   one of the four seeded scenarios in ../data/aibom_fixtures.py, by exact
   count and exact category -- not "finds something."

3. The round-trip property: a drift report that returns zero exceptions
   because everything genuinely ties has to be distinguishable from one
   that returns zero because the query is broken. Start from a
   hand-built dataset with zero drift, confirm the query agrees, then
   inject one known mismatch and confirm the query names exactly that
   one.
"""

import json
import pathlib
import sys

import duckdb
import jsonschema
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "data"))
import aibom_fixtures as fixtures  # noqa: E402

SCHEMA_DIR = pathlib.Path(__file__).parent.parent / "schema"
SQL_DIR = pathlib.Path(__file__).parent.parent / "sql"


def run_sql(con, filename: str):
    return con.sql((SQL_DIR / filename).read_text())


@pytest.fixture
def seeded_con():
    con = duckdb.connect()
    fixtures.load_into(con)
    yield con
    con.close()


def test_declared_example_validates_against_schema():
    schema = json.loads((SCHEMA_DIR / "aibom_declaration.schema.json").read_text())
    records = fixtures.load_declared()
    assert len(records) > 0
    for record in records:
        jsonschema.validate(instance=record, schema=schema)


def test_declared_example_rejects_a_malformed_record():
    """
    Proves the schema is actually restrictive, not just descriptive: a
    record with an unlisted component_type and a digest missing the
    'sha256:' prefix must fail validation, or the schema isn't doing
    anything a plain JSON parse wouldn't already do.
    """
    schema = json.loads((SCHEMA_DIR / "aibom_declaration.schema.json").read_text())
    bad_record = {
        "system": "assistant-a",
        "component_type": "vector_store",  # not one of the four allowed types
        "version": "v1",
        "digest": "not-a-real-digest",
        "effective_from": "2026-01-01T00:00:00Z",
        "declared_by": "someone",
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad_record, schema=schema)


def test_drift_detection_finds_every_seeded_scenario_by_exact_count(seeded_con):
    report = run_sql(seeded_con, "drift_detection.sql").fetchall()
    counts = {}
    for _instance_id, _system, _component_type, _observed_at, exception_type, _detail in report:
        counts[exception_type] = counts.get(exception_type, 0) + 1

    assert counts.get("VERSION_DRIFT") == 1
    assert counts.get("DIGEST_MISMATCH_SAME_VERSION_LABEL") == 1
    assert counts.get("UNDECLARED_COMPONENT") == 1
    assert counts.get("DECLARED_BUT_NEVER_OBSERVED") == 1
    assert len(report) == 4


def test_drift_detection_names_the_specific_defects(seeded_con):
    report = run_sql(seeded_con, "drift_detection.sql").fetchall()
    by_type = {row[4]: row for row in report}

    version_drift = by_type["VERSION_DRIFT"]
    assert version_drift[0] == "inst-a2"  # instance_id
    assert version_drift[1] == "assistant-a"
    assert version_drift[2] == "model"

    digest_mismatch = by_type["DIGEST_MISMATCH_SAME_VERSION_LABEL"]
    assert digest_mismatch[1:3] == ("assistant-a", "policy")

    undeclared = by_type["UNDECLARED_COMPONENT"]
    assert undeclared[1:3] == ("assistant-b", "firewall")

    never_observed = by_type["DECLARED_BUT_NEVER_OBSERVED"]
    assert never_observed[1:3] == ("assistant-a", "firewall")


def _build_clean_pair(con):
    con.execute("""
        CREATE TABLE aibom_declared (
            system VARCHAR, component_type VARCHAR, version VARCHAR,
            digest VARCHAR, effective_from TIMESTAMP, declared_by VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE aibom_observed (
            instance_id VARCHAR, system VARCHAR, component_type VARCHAR,
            version VARCHAR, digest VARCHAR, observed_at TIMESTAMP
        )
    """)
    con.execute("""
        INSERT INTO aibom_declared VALUES
            ('sys-x', 'model', 'v1', 'sha256:x-model-v1', '2026-01-01T00:00:00Z', 'release-bot')
    """)
    con.execute("""
        INSERT INTO aibom_observed VALUES
            ('inst-x1', 'sys-x', 'model', 'v1', 'sha256:x-model-v1', '2026-02-01T00:00:00Z')
    """)


def test_round_trip_clean_dataset_reports_zero_exceptions():
    con = duckdb.connect()
    _build_clean_pair(con)
    report = run_sql(con, "drift_detection.sql").fetchall()
    assert report == []
    con.close()


def test_round_trip_injected_drift_is_surfaced_and_named_exactly():
    """
    The centerpiece assertion: start from the dataset proven clean above,
    change one observed version so it no longer matches the declaration,
    and prove the query catches exactly that and nothing else. This is
    what makes the zero-exception result above trustworthy rather than
    merely convenient -- the query demonstrably fails loudly on a known,
    deliberately introduced gap.
    """
    con = duckdb.connect()
    _build_clean_pair(con)
    con.execute("UPDATE aibom_observed SET version = 'v2' WHERE instance_id = 'inst-x1'")

    report = run_sql(con, "drift_detection.sql").fetchall()
    assert len(report) == 1
    instance_id, system, component_type, _observed_at, exception_type, detail = report[0]
    assert instance_id == "inst-x1"
    assert system == "sys-x"
    assert component_type == "model"
    assert exception_type == "VERSION_DRIFT"
    assert "v2" in detail and "v1" in detail
    con.close()
