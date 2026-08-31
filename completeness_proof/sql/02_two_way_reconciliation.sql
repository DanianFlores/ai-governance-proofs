-- Two-way reconciliation: the query that actually proves completeness.
--
-- The population being certified is defined explicitly, up front, from the
-- authority (idp_source), not inferred from whatever the extract happens to
-- contain: "every identity idp_source currently marks active."
--
-- Every row that fails to reconcile is labeled with WHY it failed, so the
-- output is an exception report a reviewer can act on -- not a single
-- pass/fail number that hides which direction the defect came from.

WITH population AS (
    -- The denominator. Defined from the authoritative source, independent
    -- of anything the extract claims about itself.
    SELECT user_id, email AS source_email, department AS source_department, revoked_at
    FROM idp_source
    WHERE status = 'active'
),

extract_key_counts AS (
    SELECT user_id, COUNT(*) AS occurrences
    FROM extract
    WHERE user_id IS NOT NULL
    GROUP BY user_id
),

-- Direction 1: source -> extract. Everything the naive query in
-- 01_naive_reconciliation.sql cannot see, because it never looks this way.
missing_from_extract AS (
    SELECT
        p.user_id,
        'MISSING_FROM_EXTRACT' AS exception_type,
        'active in idp_source, absent from extract entirely' AS detail
    FROM population p
    LEFT JOIN extract e ON e.user_id = p.user_id
    WHERE e.user_id IS NULL
),

-- Direction 2: extract -> source, but restricted to identities that don't
-- exist in the source under any status. A user_id the extract invented, or
-- one the source has since deleted outright.
phantom_in_extract AS (
    SELECT DISTINCT
        e.user_id,
        'PHANTOM_IN_EXTRACT' AS exception_type,
        'present in extract, no matching identity in idp_source' AS detail
    FROM extract e
    LEFT JOIN idp_source s ON s.user_id = e.user_id
    WHERE e.user_id IS NOT NULL AND s.user_id IS NULL
),

-- Row count and distinct-key count are not the same thing. A key that
-- appears twice inflates any row-count-based coverage metric without
-- adding a single new identity to the population that's actually covered.
duplicate_keys AS (
    SELECT
        user_id,
        'DUPLICATE_KEY_IN_EXTRACT' AS exception_type,
        'user_id appears ' || occurrences || ' times in extract; expected 1' AS detail
    FROM extract_key_counts
    WHERE occurrences > 1
),

-- A NULL join key silently fails every equality-based match without ever
-- raising an error. It has to be swept up explicitly, by identity, because
-- `= NULL` and `IN (... NULL ...)` both just vanish it from every join.
null_join_keys AS (
    SELECT
        NULL AS user_id,
        'NULL_JOIN_KEY' AS exception_type,
        'extract row has NULL user_id (email on file: ' || COALESCE(TRIM(email), '<blank>') || ')' AS detail
    FROM extract
    WHERE user_id IS NULL
),

-- The extract's own status field is self-reported and can go stale. This
-- is the check the naive query skips entirely: it compares what the
-- extract claims against what the source of truth currently says, for
-- every identity that does match by key.
status_drift AS (
    SELECT
        e.user_id,
        'STATUS_DRIFT_STALE_ACTIVE' AS exception_type,
        'extract shows status=active; idp_source revoked this identity on ' || CAST(s.revoked_at AS VARCHAR) AS detail
    FROM extract e
    JOIN idp_source s ON s.user_id = e.user_id
    WHERE e.status = 'active' AND s.status != 'active'
),

-- Not a completeness defect on its own -- the identity is present and
-- correctly matched -- but worth surfacing separately so it isn't confused
-- with a genuine missing/phantom record, and so whoever owns the extract
-- pipeline knows their normalization is inconsistent.
email_format_mismatch AS (
    SELECT
        e.user_id,
        'EMAIL_FORMAT_MISMATCH_NONBLOCKING' AS exception_type,
        'extract email "' || e.email || '" vs source "' || s.source_email || '" (differs only in case/whitespace)' AS detail
    FROM extract e
    JOIN population s ON s.user_id = e.user_id
    WHERE TRIM(LOWER(e.email)) = TRIM(LOWER(s.source_email))
      AND e.email != s.source_email
)

SELECT * FROM missing_from_extract
UNION ALL SELECT * FROM phantom_in_extract
UNION ALL SELECT * FROM duplicate_keys
UNION ALL SELECT * FROM null_join_keys
UNION ALL SELECT * FROM status_drift
UNION ALL SELECT * FROM email_format_mismatch
ORDER BY exception_type, user_id;
