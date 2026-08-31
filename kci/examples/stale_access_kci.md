# Worked example: Stale Access Non-Removal Rate

All seven fields from [`format.md`](../format.md), filled out against the
synthetic fixture in [`../data/fixtures.py`](../data/fixtures.py). Every
number below is checked exactly by
[`../tests/test_delta_attribution.py`](../tests/test_delta_attribution.py)
-- nothing here is asserted only in prose.

## 1. Indicator name & control objective

**Stale Access Non-Removal Rate.** Of every identity revoked in the
authoritative identity source, what fraction does the downstream system
still show as having active access, as of the measurement date? Control
objective: *access is removed from downstream systems within a bounded
window of revocation in the source of truth.* This is the same
`STATUS_DRIFT_STALE_ACTIVE` defect category
[`completeness_proof/sql/02_two_way_reconciliation.sql`](../../completeness_proof/sql/02_two_way_reconciliation.sql)
defines for a single point in time -- this KCI tracks it across two.

## 2. Population definition

Every identity in `identities` with a non-NULL `revoked_at` on or before
the snapshot date. Defined from `identities.revoked_at` (the authority),
not from anything `extract_observations` (the downstream system) claims
about itself -- same discipline as `completeness_proof`'s `population` CTE.

## 3. Measurement logic, with a version identifier

- **`logic_v1`** ([`../sql/logic_v1_no_grace.sql`](../sql/logic_v1_no_grace.sql)):
  numerator = revoked identities the extract still shows as `active` at
  that snapshot; denominator = the full revoked population as of that
  snapshot. No exceptions.
- **`logic_v2`** ([`../sql/logic_v2_grace_period.sql`](../sql/logic_v2_grace_period.sql)):
  same, excluding identities revoked within 2 days of the snapshot from
  both sides of the ratio.

| Snapshot | Logic | Revoked population | Stale count | KCI |
|---|---|---|---|---|
| A (2026-07-31) | v1 | 5 | 3 | 60.0% |
| A (2026-07-31) | v2 | 4 | 2 | 50.0% |
| B (2026-08-31) | v1 | 7 | 2 | 28.6% |
| B (2026-08-31) | v2 | 6 | 1 | 16.7% |

## 4. Threshold / target

Synthetic threshold for this example: **amber above 10%, red above 25%**,
reviewed by the (synthetic) access-governance owner every two quarters.
The number itself carries no real-world rationale -- see the repo-level
constraint that no production thresholds or their business justification
appear anywhere in this repo.

## 5. Evidence source & collection mechanism

Synthetic: `identities.revoked_at` is presented as a nightly automated
pull from the identity source; `extract_observations` as a nightly
automated pull from the downstream system's own access report. Both fully
automated, no manual attestation step -- stated explicitly, because a KCI
built on a manual quarterly export deserves a visibly different trust
level than one rebuilt from source systems every night, and this field is
where that difference has to be written down rather than assumed.

## 6. Owner & escalation path

Synthetic: access-governance control owner. Breach of the amber threshold
files a ticket against the downstream system's engineering owner with a
5-business-day SLA; breach of red escalates to the control owner's
manager same-day.

## 7. Change log

| Date | Author | Change | Reason |
|---|---|---|---|
| 2026-07-31 | (synthetic) control owner | Defined `logic_v1`, no grace period | Initial definition |
| 2026-08-15 | (synthetic) control owner | Added `logic_v2`: 2-day propagation grace period | The downstream system's own deprovisioning job runs on a schedule with up to ~48h of expected lag; `logic_v1` was counting that expected lag as a control failure identically to genuine non-removal, which meant the metric could never reach 0% even with a perfectly functioning control. Kept `logic_v1` in the repo rather than deleting it, specifically so the effect of this change is measurable -- see the delta attribution below. |

---

## Why this needs delta attribution, not just a trend line

Between period A and period B the reported number moves from 60.0%
(`logic_v1`) to 16.7% (`logic_v2`) -- a huge apparent improvement. But two
things changed at once: the underlying revoked population moved from A to
B (some stale identities got remediated, one new revocation hasn't
propagated yet), *and* the measurement logic itself changed (the grace
period was added partway through). A KCI history that only shows the
headline number can't tell a reviewer how much of that -43.3 percentage
point swing is a real improvement in the control versus a redefinition of
what counts as a defect.

[`../sql/delta_attribution.sql`](../sql/delta_attribution.sql) answers
that, and -- just as importantly -- shows that the answer depends on which
order you attribute the two effects in:

| Attribution order | Population effect | Logic effect | Reconstructed total |
|---|---|---|---|
| Population first, then logic | -31.43 pp | -11.90 pp | -43.33 pp |
| Logic first, then population | -10.00 pp | -33.33 pp | -43.33 pp |

Both orderings reconstruct the same total exactly (that part is just
arithmetic). But they disagree with each other by about 1.9 percentage
points on how much of the swing to call "population" versus "logic" --
because the two effects interact, and which one you measure first absorbs
that interaction into itself. Reporting a single ordering's split without
saying so is how "we tightened the definition" quietly becomes "the
control got better," or vice versa.
[`../tests/test_delta_attribution.py`](../tests/test_delta_attribution.py)
asserts that interaction term is nonzero on this dataset, precisely so a
future edit that accidentally made the two effects independent (and the
whole "report both orderings" argument moot) would get caught rather than
pass silently.
