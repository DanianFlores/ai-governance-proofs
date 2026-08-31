-- Naive reconciliation: the query most people write.
--
-- It answers "how much of the extract matches the source?" -- which is the
-- wrong question. The extract is checking itself against the source, not
-- the other way around. The denominator here is the extract's own row
-- count, not the population the extract is supposed to represent.

WITH matched AS (
    SELECT e.user_id
    FROM extract e
    WHERE e.user_id IN (SELECT user_id FROM idp_source)
)
SELECT
    (SELECT COUNT(*) FROM extract)                       AS extract_row_count,
    (SELECT COUNT(*) FROM matched)                        AS matched_row_count,
    ROUND(
        (SELECT COUNT(*) FROM matched) * 100.0
        / NULLIF((SELECT COUNT(*) FROM extract), 0),
        1
    )                                                      AS reported_coverage_pct;

-- What this number cannot see, and why:
--
-- 1. Missing rows. 24 active identities in idp_source never made it into
--    the extract at all. A one-directional "does this extract row exist in
--    the source" check never looks at the source's side of the relationship,
--    so it cannot detect anything the extract failed to include. This is the
--    core blind spot: an extract cannot validate itself, and neither can a
--    query that only walks outward from it.
--
-- 2. Duplicates. 8 identities appear twice in the extract. `matched_row_count`
--    counts rows, not distinct keys, so each duplicate is silently counted
--    as two units of "coverage" instead of flagged as a data quality defect.
--
-- 3. The NULL join key. One extract row has user_id = NULL. In standard SQL,
--    `NULL IN (SELECT user_id FROM idp_source)` evaluates to NULL, which is
--    falsy in a WHERE clause -- so that row is silently excluded from
--    `matched`, but nothing here says why, or that it happened at all. It
--    just quietly deflates the count with no signal attached.
--
-- 4. Status drift. 12 identities the source has since revoked are still
--    listed as status='active' in the extract. This query only checks that
--    the user_id exists somewhere in idp_source -- it never compares the
--    extract's claimed status against the source's current status. A
--    revoked identity with lingering "active" access is exactly the kind of
--    thing a completeness check exists to catch, and this query is blind to
--    it because it was never asked the question.
--
-- 5. Phantom rows happen to get caught here (they fail the IN check), but
--    only as an artifact of one specific direction of the join -- not
--    because the query was designed to look for them.
--
-- Net effect: this query will report a coverage number in the high 90s that
-- feels reassuring and proves almost nothing. A query returning a clean
-- number because the denominator is wrong looks identical to one returning
-- a clean number because everything actually ties.
