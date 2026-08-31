-- KCI logic v2: Stale Access Non-Removal Rate, with a 2-day propagation
-- grace period.
--
-- Same definition as logic_v1_no_grace.sql, with one change: an identity
-- revoked within 2 days of the snapshot date is excluded from BOTH the
-- population and the stale count. The rationale (see
-- examples/stale_access_kci.md's change log) is that the downstream
-- system has a known propagation lag, so counting an identity as a defect
-- before it has had a reasonable window to deprovision penalizes the
-- control for its own measurement cadence rather than for an actual
-- failure to remove access.
--
-- This is exactly the kind of change field 3 of format.md exists to
-- force a version identifier onto: it moves the reported number without
-- the underlying access-removal behavior having changed at all. See
-- delta_attribution.sql for how that movement is told apart from a
-- genuine change in the revoked population.

WITH revoked_population AS (
    SELECT i.user_id, sp.period
    FROM identities i
    CROSS JOIN snapshot_periods sp
    WHERE i.revoked_at IS NOT NULL
      AND i.revoked_at <= sp.snapshot_date
      -- The grace exclusion: date_diff in whole days between revocation
      -- and the snapshot must exceed 2 for the identity to count at all.
      AND date_diff('day', i.revoked_at, sp.snapshot_date) > 2
),

stale AS (
    SELECT rp.user_id, rp.period
    FROM revoked_population rp
    JOIN extract_observations eo
      ON eo.user_id = rp.user_id AND eo.period = rp.period AND eo.status = 'active'
)

SELECT
    rp.period,
    COUNT(DISTINCT rp.user_id)   AS revoked_population,
    COUNT(DISTINCT s.user_id)     AS stale_count,
    COUNT(DISTINCT s.user_id) * 100.0 / NULLIF(COUNT(DISTINCT rp.user_id), 0) AS kci_pct_exact,
    ROUND(COUNT(DISTINCT s.user_id) * 100.0 / NULLIF(COUNT(DISTINCT rp.user_id), 0), 1) AS kci_pct
FROM revoked_population rp
LEFT JOIN stale s ON s.user_id = rp.user_id AND s.period = rp.period
GROUP BY rp.period
ORDER BY rp.period;
