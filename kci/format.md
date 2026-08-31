# KCI definition format

A Key Control Indicator is a metric that stands in for "is this control
working." That substitution only holds if the indicator's definition is
written down precisely enough that two different people computing it from
the same underlying data get the same number -- and that any later change
to the definition is itself recorded, not silently absorbed into the trend
line.

Seven fields, each closing a specific way KCIs go soft in practice.

## 1. Indicator name & control objective

The name, plus one sentence stating the control risk this indicator stands
in for, phrased as a testable claim ("access is removed within N days of
revocation"), not a goal ("we manage access well"). If the objective
sentence can't fail, it isn't one.

## 2. Population definition

What the denominator is, defined from an authoritative source, independent
of whatever the measurement's own data happens to contain. This is the
same discipline [`completeness_proof/`](../completeness_proof/) exists to
demonstrate: a population inferred from an extract can only ever validate
the extract against itself.

## 3. Measurement logic, with a version identifier

The numerator/denominator computation, plus an explicit `logic_version`.
Measurement logic changes over time -- grace periods get added, edge cases
get reclassified, a join gets fixed. Every one of those changes moves the
reported number, for reasons that have nothing to do with the control
getting better or worse. Without a version identifier attached to every
historical value, a logic change and a real change in control performance
are indistinguishable from the trend line alone. See
[`sql/delta_attribution.sql`](sql/delta_attribution.sql) for what happens
when you have to tell them apart.

## 4. Threshold / target

The pass/fail (or amber/red) line, and a cadence for revisiting it. A
threshold is a policy decision, not a physical constant -- it should be
owned and periodically re-justified, not set once and forgotten until an
audit asks where it came from.

## 5. Evidence source & collection mechanism

Where the numerator and denominator actually come from: which system of
record, queried how (automated pull vs. manual attestation), on what
refresh cadence. A KCI backed by a quarterly manual spreadsheet and one
backed by a nightly automated query can carry the identical definition and
still deserve very different levels of trust -- this field is what tells a
reviewer which one they're looking at.

## 6. Owner & escalation path

Who is accountable when the indicator breaches threshold, and what
concretely happens next -- not "gets notified," but the actual next step
(ticket filed against whom, by when, escalates to whom if unresolved).

## 7. Change log

Every revision to fields 2 through 4 (population, logic, threshold),
recorded with date, author, and reason. This is what field 3's version
identifier is *for* -- a KCI whose definition can change without a record
is not continuous evidence, it's a moving target with a number attached.

---

See [`examples/stale_access_kci.md`](examples/stale_access_kci.md) for all
seven fields filled out against a synthetic scenario, and
[`sql/delta_attribution.sql`](sql/delta_attribution.sql) for a worked
proof of why field 3's versioning is load-bearing and not paperwork.
