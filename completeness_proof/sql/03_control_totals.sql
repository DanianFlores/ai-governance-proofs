-- Control totals: a cheap, coarse tripwire you run before -- or alongside --
-- the full exception report.
--
-- Row count and distinct count catch different things (a duplicate moves
-- row_count but not distinct_key_count). The content checksum is order-
-- independent -- built with SUM() over a per-row hash, which is commutative,
-- so it doesn't matter what order either table's rows come back in. Two
-- tables with the same rows in different order still produce the same
-- checksum; two tables with even one differing row do not.
--
-- This does NOT replace 02_two_way_reconciliation.sql. A checksum mismatch
-- tells you something differs; it does not tell you what, or which
-- direction. It's a fast "should I go run the detailed report" signal, not
-- a substitute for it. And a checksum match on a badly-built query is worth
-- exactly as much as a coverage number on a badly-built query: see the note
-- at the bottom on why a zero-diff result needs its own proof.

WITH population_content AS (
    -- Same population definition as the reconciliation query: active
    -- identities per the authoritative source. Content is normalized
    -- (lowercased, trimmed) so formatting alone can't move the checksum --
    -- that's what 02's EMAIL_FORMAT_MISMATCH_NONBLOCKING category is for.
    SELECT
        user_id,
        TRIM(LOWER(email)) || '|' || department AS normalized_content
    FROM idp_source
    WHERE status = 'active'
),

extract_content AS (
    -- Deduplicated by user_id so a duplicated row doesn't get double-
    -- counted into the checksum; duplicates are their own exception
    -- category in 02, not a completeness signal here.
    SELECT DISTINCT
        user_id,
        TRIM(LOWER(email)) || '|' || department AS normalized_content
    FROM extract
    WHERE user_id IS NOT NULL
      AND status = 'active'
)

SELECT
    'idp_source (active population)' AS side,
    COUNT(*)                                        AS row_count,
    COUNT(DISTINCT user_id)                          AS distinct_key_count,
    SUM(HASH(user_id || '|' || normalized_content))  AS content_checksum
FROM population_content

UNION ALL

SELECT
    'extract (deduplicated, active only)' AS side,
    COUNT(*)                                        AS row_count,
    COUNT(DISTINCT user_id)                          AS distinct_key_count,
    SUM(HASH(user_id || '|' || normalized_content))  AS content_checksum
FROM extract_content;

-- Reading this output:
--
--   row_count / distinct_key_count matching within a side confirms that
--   side, at least, has no duplicate keys after dedup (extract_content
--   already deduped, so this is really a sanity check on the CTE itself).
--
--   content_checksum differing between the two sides confirms the sides
--   disagree on membership or content -- consistent with the
--   MISSING_FROM_EXTRACT, PHANTOM_IN_EXTRACT, and STATUS_DRIFT_STALE_ACTIVE
--   rows the detailed report in 02 will enumerate by name.
--
--   content_checksum MATCHING between the two sides is the case that needs
--   the most scrutiny, not the least. See tests/test_round_trip.py: a
--   checksum query that's silently broken (wrong join, empty table, a typo
--   that makes both sides evaluate to the same constant) also reports a
--   match. The round-trip test exists precisely because "checksums tie"
--   and "the query is broken" are indistinguishable from the number alone
--   -- you have to inject a known defect and prove it gets caught.
