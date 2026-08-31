"""
Loads the declared AI Bill of Materials (from
../examples/synthcorp_declared.json, the schema-validated source of
truth -- see ../schema/format.md) plus a synthetic, hand-authored
runtime-observation log into DuckDB, for the drift-detection query in
../sql/drift_detection.sql.

Only the declared side has a published schema: it's the governance
artifact this module defines. The observed side represents whatever a
system's own runtime telemetry happens to report -- hand-authored here,
small enough to check by eye, deliberately covering four scenarios:

  assistant-a / model     -- one instance catches up a declared version
                              bump one observation late (a normal,
                              self-resolving mid-rollout drift).
  assistant-a / prompt     -- clean throughout.
  assistant-a / policy     -- the version label matches the current
                              declaration but the digest doesn't (a
                              same-label, different-build defect).
  assistant-a / firewall   -- declared, but never appears in any
                              observation at all (a coverage blind spot,
                              not a version mismatch).
  assistant-b / model      -- clean throughout.
  assistant-b / firewall   -- observed running, but assistant-b has no
                              firewall declaration in its history at all
                              (a shadow deployment).

Everything here is fabricated; "assistant-a" and "assistant-b" are
placeholder synthetic systems, not references to any real product.
"""

from __future__ import annotations

import json
import pathlib

EXAMPLES_DIR = pathlib.Path(__file__).parent.parent / "examples"
DECLARED_JSON = EXAMPLES_DIR / "synthcorp_declared.json"

# (instance_id, system, component_type, version, digest, observed_at)
OBSERVED = [
    ("inst-a1", "assistant-a", "model", "v2", "sha256:model-v2", "2026-08-16T00:00:00Z"),
    ("inst-a2", "assistant-a", "model", "v1", "sha256:model-v1", "2026-08-16T00:00:00Z"),
    ("inst-a2", "assistant-a", "model", "v2", "sha256:model-v2", "2026-08-20T00:00:00Z"),
    ("inst-a1", "assistant-a", "prompt", "v5", "sha256:prompt-v5", "2026-08-16T00:00:00Z"),
    ("inst-a1", "assistant-a", "policy", "v3", "sha256:policy-v3-stale-build", "2026-08-25T00:00:00Z"),
    ("inst-a2", "assistant-a", "policy", "v2", "sha256:policy-v2", "2026-08-10T00:00:00Z"),
    ("inst-b1", "assistant-b", "model", "b-v1", "sha256:b-model-v1", "2026-08-16T00:00:00Z"),
    ("inst-b1", "assistant-b", "firewall", "b-fw-v1", "sha256:b-firewall-v1", "2026-08-16T00:00:00Z"),
]


def load_declared() -> list[dict]:
    return json.loads(DECLARED_JSON.read_text())


def load_into(con, declared: list[dict] | None = None, observed: list[tuple] | None = None) -> None:
    """Create aibom_declared and aibom_observed tables in the given DuckDB connection."""
    if declared is None:
        declared = load_declared()
    if observed is None:
        observed = OBSERVED

    con.execute("""
        CREATE OR REPLACE TABLE aibom_declared (
            system          VARCHAR,
            component_type  VARCHAR,
            version         VARCHAR,
            digest          VARCHAR,
            effective_from  TIMESTAMP,
            declared_by     VARCHAR
        )
    """)
    con.execute("""
        CREATE OR REPLACE TABLE aibom_observed (
            instance_id     VARCHAR,
            system          VARCHAR,
            component_type  VARCHAR,
            version         VARCHAR,
            digest          VARCHAR,
            observed_at     TIMESTAMP
        )
    """)

    con.executemany(
        "INSERT INTO aibom_declared VALUES (?, ?, ?, ?, ?, ?)",
        [
            (d["system"], d["component_type"], d["version"], d["digest"], d["effective_from"], d["declared_by"])
            for d in declared
        ],
    )
    con.executemany("INSERT INTO aibom_observed VALUES (?, ?, ?, ?, ?, ?)", observed)


if __name__ == "__main__":
    import duckdb

    here = pathlib.Path(__file__).parent
    db_path = here / "aibom_evidence.duckdb"
    db_path.unlink(missing_ok=True)

    con = duckdb.connect(str(db_path))
    load_into(con)
    con.close()

    print(f"built {db_path.name}: {len(load_declared())} declared records, {len(OBSERVED)} observations")
