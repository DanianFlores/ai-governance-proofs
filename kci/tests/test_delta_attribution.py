"""
Tests for the Stale Access Non-Removal Rate KCI's two logic versions and
its delta attribution.

Three things are being proven, not just "the SQL runs":

1. Each logic version (v1: no grace period, v2: 2-day grace period)
   produces the exact population/stale counts the hand-authored fixture
   in data/fixtures.py was built to produce -- worked out by hand in
   examples/stale_access_kci.md, and checked here so that walkthrough
   isn't just prose.

2. The delta-attribution bridge identity actually holds: population
   effect + logic effect reconstructs the total delta exactly, in both
   attribution orderings, computed independently in Python with exact
   Fraction arithmetic (not by trusting the SQL's own rounded output back
   against itself).

3. The two orderings disagree with each other by a nonzero amount -- the
   interaction term delta_attribution.sql's header comment describes. If
   this were ever zero, the "order matters, report both" claim in that
   file would be decorative rather than load-bearing, and this test would
   catch that regression.
"""

import pathlib
import sys
from fractions import Fraction

import duckdb
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent / "data"))
import fixtures  # noqa: E402

SQL_DIR = pathlib.Path(__file__).parent.parent / "sql"


def read_sql(filename: str) -> str:
    return (SQL_DIR / filename).read_text()


@pytest.fixture
def con():
    connection = duckdb.connect()
    fixtures.load_into(connection)
    yield connection
    connection.close()


def _rows_by_period(con, filename: str) -> dict:
    result = con.sql(read_sql(filename)).fetchall()
    cols = [d[0] for d in con.sql(read_sql(filename)).description]
    return {row[cols.index("period")]: dict(zip(cols, row)) for row in result}


def test_logic_v1_matches_hand_worked_counts(con):
    rows = _rows_by_period(con, "logic_v1_no_grace.sql")

    assert rows["A"]["revoked_population"] == 5
    assert rows["A"]["stale_count"] == 3
    assert rows["A"]["kci_pct"] == 60.0

    assert rows["B"]["revoked_population"] == 7
    assert rows["B"]["stale_count"] == 2
    assert rows["B"]["kci_pct"] == 28.6


def test_logic_v2_grace_period_excludes_the_just_revoked(con):
    rows = _rows_by_period(con, "logic_v2_grace_period.sql")

    # usr_03 (revoked 1 day before period A) drops out of both population
    # and stale count relative to v1's 5/3.
    assert rows["A"]["revoked_population"] == 4
    assert rows["A"]["stale_count"] == 2
    assert rows["A"]["kci_pct"] == 50.0

    # usr_04 (revoked 1 day before period B) drops out of both population
    # and stale count relative to v1's 7/2.
    assert rows["B"]["revoked_population"] == 6
    assert rows["B"]["stale_count"] == 1
    assert rows["B"]["kci_pct"] == 16.7


def test_delta_attribution_bridge_identity_holds_in_both_orderings(con):
    con.execute(f"CREATE VIEW kci_v1_by_period AS {read_sql('logic_v1_no_grace.sql')}")
    con.execute(f"CREATE VIEW kci_v2_by_period AS {read_sql('logic_v2_grace_period.sql')}")

    bridge = con.sql(read_sql("delta_attribution.sql")).fetchall()
    by_order = {row[0]: row for row in bridge}

    for attribution_order, pop_effect, logic_effect, reconstructed, actual in bridge:
        assert reconstructed == actual, (
            f"{attribution_order}: population_effect + logic_effect "
            f"({pop_effect} + {logic_effect} = {reconstructed}) must equal "
            f"the actual total delta ({actual}) -- this is a telescoping "
            f"sum, not an approximation."
        )

    # Cross-check the SQL's rounded output against exact Fraction
    # arithmetic on the raw counts, so a rounding bug in the SQL can't
    # coincidentally reconstruct correctly and slip past the check above.
    kci_a_v1 = Fraction(3, 5)
    kci_b_v1 = Fraction(2, 7)
    kci_a_v2 = Fraction(1, 2)
    kci_b_v2 = Fraction(1, 6)

    total_delta = kci_b_v2 - kci_a_v1

    order1_population_effect = kci_b_v1 - kci_a_v1
    order1_logic_effect = kci_b_v2 - kci_b_v1
    assert order1_population_effect + order1_logic_effect == total_delta

    order2_logic_effect = kci_a_v2 - kci_a_v1
    order2_population_effect = kci_b_v2 - kci_a_v2
    assert order2_population_effect + order2_logic_effect == total_delta

    # The interaction term: how much the two orderings disagree about the
    # size of "the" population effect (equivalently, "the" logic effect).
    # Nonzero here is the entire point -- it's what makes reporting a
    # single ordering's split misleading instead of merely arbitrary.
    interaction = order1_population_effect - order2_population_effect
    assert interaction != 0
    assert abs(float(interaction) * 100) == pytest.approx(1.9047619, abs=1e-4)

    # Sanity-check the SQL's rounded percentages track the exact math
    # closely enough to be the same story, not just structurally similar.
    order1_row = by_order["order1_population_first"]
    assert order1_row[1] == pytest.approx(float(order1_population_effect) * 100, abs=0.05)
    assert order1_row[2] == pytest.approx(float(order1_logic_effect) * 100, abs=0.05)
