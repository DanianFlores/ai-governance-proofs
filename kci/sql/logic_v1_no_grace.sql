-- KCI logic v1: Stale Access Non-Removal Rate, no propagation grace period.
--
-- Definition: of every identity idp_source has revoked as of a snapshot's
-- date, what fraction does the downstream extract still show as
-- status='active' at that snapshot?
--
-- This version does not exempt recently-revoked identities from either
-- side of the ratio: an identity revoked one day before the snapshot is
-- judged identically to one revoked six months ago. See
-- logic_v2_grace_period.sql for the alternative definition that adds a
-- propagation grace period, and delta_attribution.sql for why the two
-- versions have to be told apart rather than just diffed against each
-- other as if the underlying population were all that changed.
--
-- Returns one row per period (this dataset has two: 'A' and 'B').

WITH revoked_population AS (
    -- The denominator, defined from the authority (identities.revoked_at)
    -- as of each snapshot date -- not from anything the extract claims.
    SELECT i.user_id, sp.period
    FROM identities i
    CROSS JOIN snapshot_periods sp
    WHERE i.revoked_at IS NOT NULL
      AND i.revoked_at <= sp.snapshot_date
),

stale AS (
    -- Revoked identities the extract still shows as active at that same
    -- snapshot -- the STATUS_DRIFT_STALE_ACTIVE category from
    -- completeness_proof/sql/02_two_way_reconciliation.sql, computed here
    -- against two points in time instead of one.
    SELECT rp.user_id, rp.period
    FROM revoked_population rp
    JOIN extract_observations eo
      ON eo.user_id = rp.user_id AND eo.period = rp.period AND eo.status = 'active'
)

SELECT
    rp.period,
    COUNT(DISTINCT rp.user_id)   AS revoked_population,
    COUNT(DISTINCT s.user_id)     AS stale_count,
    -- Full precision, for anything downstream (delta_attribution.sql) that
    -- needs to do arithmetic on this number without compounding rounding.
    COUNT(DISTINCT s.user_id) * 100.0 / NULLIF(COUNT(DISTINCT rp.user_id), 0) AS kci_pct_exact,
    -- Rounded, for a human reading this table directly.
    ROUND(COUNT(DISTINCT s.user_id) * 100.0 / NULLIF(COUNT(DISTINCT rp.user_id), 0), 1) AS kci_pct
FROM revoked_population rp
LEFT JOIN stale s ON s.user_id = rp.user_id AND s.period = rp.period
GROUP BY rp.period
ORDER BY rp.period;
