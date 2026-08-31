-- Drift detection: compares what was declared against what was actually
-- observed running, in both directions -- the same lesson
-- completeness_proof/sql/02_two_way_reconciliation.sql establishes for
-- an access extract, applied here to a component inventory instead.
--
-- The central difficulty this query exists to handle: the declared side
-- is a changelog, not a snapshot (see ../schema/format.md). "What's
-- declared right now" is the wrong question to ask about an observation
-- from three weeks ago, mid-rollout. The right question is "what was
-- declared as of the moment this observation happened" -- an as-of join,
-- not an equality join.

WITH declared_as_of AS (
    -- For every observation, find the declaration in effect at that
    -- exact moment: the most recent declared row for the same
    -- (system, component_type) whose effective_from is not after the
    -- observation. QUALIFY + ROW_NUMBER picks that single row per
    -- observation; when no declared row qualifies at all (nothing was
    -- ever declared for this system/component_type by that time), the
    -- LEFT JOIN leaves every declared_* column NULL, and that NULL row is
    -- still the "closest" one there is, so it survives the QUALIFY too --
    -- which is exactly the signal undeclared_component below reads.
    SELECT
        o.instance_id,
        o.system,
        o.component_type,
        o.observed_at,
        o.version   AS observed_version,
        o.digest     AS observed_digest,
        d.version   AS declared_version,
        d.digest     AS declared_digest,
        d.effective_from AS declared_effective_from
    FROM aibom_observed o
    LEFT JOIN aibom_declared d
        ON d.system = o.system
       AND d.component_type = o.component_type
       AND d.effective_from <= o.observed_at
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY o.instance_id, o.system, o.component_type, o.observed_at
        ORDER BY d.effective_from DESC
    ) = 1
),

-- Direction 1, case a: something is running that was never declared at
-- all for this system/component_type, at any point before it was
-- observed. Not a version mismatch -- there is no declared version to
-- mismatch against. A shadow deployment, or a component type nobody
-- ever formally declared for this system.
undeclared_component AS (
    SELECT
        instance_id, system, component_type, observed_at,
        'UNDECLARED_COMPONENT' AS exception_type,
        system || '/' || component_type || ': instance ' || instance_id ||
            ' reports version ' || observed_version ||
            ', but no declaration exists for this system/component_type as of ' ||
            CAST(observed_at AS VARCHAR) AS detail
    FROM declared_as_of
    WHERE declared_version IS NULL
),

-- Direction 1, case b: a declaration exists as of the observation time,
-- but the running version doesn't match it.
version_drift AS (
    SELECT
        instance_id, system, component_type, observed_at,
        'VERSION_DRIFT' AS exception_type,
        system || '/' || component_type || ': instance ' || instance_id ||
            ' reports version ' || observed_version || ', declared version as of ' ||
            CAST(observed_at AS VARCHAR) || ' was ' || declared_version ||
            ' (effective ' || CAST(declared_effective_from AS VARCHAR) || ')' AS detail
    FROM declared_as_of
    WHERE declared_version IS NOT NULL
      AND observed_version != declared_version
),

-- Direction 1, case c: the version label matches, but the content
-- doesn't. A version string is a claim; the digest is what actually
-- identifies the artifact. Two builds retagged with the same label look
-- identical under version_drift's check and only diverge here.
digest_mismatch AS (
    SELECT
        instance_id, system, component_type, observed_at,
        'DIGEST_MISMATCH_SAME_VERSION_LABEL' AS exception_type,
        system || '/' || component_type || ': instance ' || instance_id ||
            ' reports version ' || observed_version || ' matching the declaration, but digest ' ||
            observed_digest || ' != declared digest ' || declared_digest AS detail
    FROM declared_as_of
    WHERE declared_version IS NOT NULL
      AND observed_version = declared_version
      AND observed_digest != declared_digest
),

-- Direction 2: the reverse check version_drift/undeclared_component
-- cannot do, because they only ever look outward from an observation
-- that exists. A component currently declared but never confirmed by any
-- observation, at any time, is a blind spot no amount of per-observation
-- checking can see -- exactly the MISSING_FROM_EXTRACT lesson from
-- completeness_proof, reapplied: the population has to be defined from
-- the authority (what's currently declared) and checked against what
-- was actually seen, not inferred from the observation log alone.
current_declared AS (
    SELECT system, component_type, version, effective_from
    FROM aibom_declared d
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY system, component_type
        ORDER BY effective_from DESC
    ) = 1
),

declared_but_never_observed AS (
    SELECT
        NULL AS instance_id,
        cd.system, cd.component_type,
        NULL AS observed_at,
        'DECLARED_BUT_NEVER_OBSERVED' AS exception_type,
        cd.system || '/' || cd.component_type || ': currently declared as ' || cd.version ||
            ' (effective ' || CAST(cd.effective_from AS VARCHAR) ||
            '), but no observation of this system/component_type exists at any version' AS detail
    FROM current_declared cd
    LEFT JOIN aibom_observed o
        ON o.system = cd.system AND o.component_type = cd.component_type
    WHERE o.system IS NULL
)

SELECT * FROM undeclared_component
UNION ALL SELECT * FROM version_drift
UNION ALL SELECT * FROM digest_mismatch
UNION ALL SELECT * FROM declared_but_never_observed
ORDER BY exception_type, system, component_type, observed_at;
