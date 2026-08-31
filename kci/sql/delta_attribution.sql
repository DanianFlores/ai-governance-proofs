-- Delta attribution: decomposes the change in the Stale Access
-- Non-Removal Rate between two snapshot dates into how much of the
-- movement came from the underlying revoked population changing versus
-- how much came from changing the measurement logic itself (the v1 -> v2
-- grace-period change defined in logic_v1_no_grace.sql /
-- logic_v2_grace_period.sql).
--
-- Depends on two views that must already exist in the connection:
--   kci_v1_by_period(period, revoked_population, stale_count, kci_pct_exact, kci_pct)
--   kci_v2_by_period(period, revoked_population, stale_count, kci_pct_exact, kci_pct)
-- -- i.e. the result of running logic_v1_no_grace.sql and
-- logic_v2_grace_period.sql, registered as views. See
-- tests/test_delta_attribution.py for exactly how.
--
-- Why two orderings, not one:
--
-- A KCI's total change between two periods can be decomposed by asking
-- "what if only the population had moved" and "what if only the logic had
-- moved" -- but which one you hold fixed while measuring the other
-- changes the answer you get. Order 1 measures the population effect
-- first (logic held at v1, population A -> B), then the logic effect
-- against the new population (v1 -> v2, held at period B). Order 2
-- measures the logic effect first (v1 -> v2, held at period A), then the
-- population effect under the new logic (population A -> B, held at v2).
--
-- Both orderings sum exactly to the same total delta -- that's arithmetic,
-- not a claim -- but the individual population/logic splits they produce
-- differ whenever the two effects interact, which they do here (see
-- tests/test_delta_attribution.py for the exact, nonzero interaction
-- term). Reporting only one ordering's split, without saying which one,
-- lets you pick whichever story flatters the narrative you want to tell
-- ("the population got worse" vs. "we just tightened the definition").
-- Showing both orderings -- and the gap between them -- is the honest
-- answer; hiding the gap is how a real change in control performance gets
-- laundered into "we improved our measurement."

WITH a_v1 AS (SELECT * FROM kci_v1_by_period WHERE period = 'A'),
     b_v1 AS (SELECT * FROM kci_v1_by_period WHERE period = 'B'),
     a_v2 AS (SELECT * FROM kci_v2_by_period WHERE period = 'A'),
     b_v2 AS (SELECT * FROM kci_v2_by_period WHERE period = 'B'),

     total_delta AS (
         SELECT b_v2.kci_pct_exact - a_v1.kci_pct_exact AS value
         FROM b_v2, a_v1
     ),

     -- Order 1: population effect (A->B) measured under v1, then the
     -- logic effect (v1->v2) measured at period B.
     order1 AS (
         SELECT
             b_v1.kci_pct_exact - a_v1.kci_pct_exact AS population_effect,
             b_v2.kci_pct_exact - b_v1.kci_pct_exact AS logic_effect
         FROM a_v1, b_v1, b_v2
     ),

     -- Order 2: logic effect (v1->v2) measured at period A, then the
     -- population effect (A->B) measured under v2.
     order2 AS (
         SELECT
             a_v2.kci_pct_exact - a_v1.kci_pct_exact AS logic_effect,
             b_v2.kci_pct_exact - a_v2.kci_pct_exact AS population_effect
         FROM a_v1, a_v2, b_v2
     )

SELECT
    'order1_population_first'                          AS attribution_order,
    ROUND(order1.population_effect, 2)                 AS population_effect_pp,
    ROUND(order1.logic_effect, 2)                       AS logic_effect_pp,
    ROUND(order1.population_effect + order1.logic_effect, 2) AS reconstructed_total_pp,
    ROUND(total_delta.value, 2)                          AS actual_total_delta_pp
FROM order1, total_delta

UNION ALL

SELECT
    'order2_logic_first'                                AS attribution_order,
    ROUND(order2.population_effect, 2)                  AS population_effect_pp,
    ROUND(order2.logic_effect, 2)                        AS logic_effect_pp,
    ROUND(order2.population_effect + order2.logic_effect, 2) AS reconstructed_total_pp,
    ROUND(total_delta.value, 2)                          AS actual_total_delta_pp
FROM order2, total_delta;

-- Reading this output:
--
--   reconstructed_total_pp should equal actual_total_delta_pp on every row
--   -- that's the telescoping-sum identity, and if it doesn't hold the
--   query has a bug, not an interesting finding.
--
--   population_effect_pp and logic_effect_pp differing between the two
--   rows for the SAME conceptual quantity is the actual finding: it's the
--   interaction between the two effects, and it's why this module reports
--   both orderings instead of picking one and calling it "the" breakdown.
