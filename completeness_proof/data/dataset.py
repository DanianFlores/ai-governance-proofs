"""
Synthetic dataset generator for the completeness-proof demo.

Everything here is fabricated. There is no real IdP, no real tenant, no real
user. The generator is deterministic (fixed seed) so anyone running it gets
byte-identical output, which is what lets the round-trip test in
tests/test_round_trip.py make exact assertions.

Two tables are produced:

  idp_source  -- the authoritative identity roster. This is the thing that
                 defines "complete." 1,150 identities: 1,000 active,
                 150 revoked (revoked_at set).

  extract     -- an access-certification extract that CLAIMS to contain
                 every active identity from idp_source. It does not.
                 Known defects are seeded in on purpose (see DEFECTS below)
                 so the reconciliation queries have something real to catch.

The IdP source is the source of truth for who is currently active. The
extract's own `status` column is just what the downstream system believes --
which is exactly the kind of stale, self-reported field a completeness
proof has to check against the authority, not trust at face value.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

SEED = 42

N_ACTIVE = 1000
N_REVOKED = 150

# Defect counts, applied to the extract relative to idp_source's active population.
N_MISSING = 24          # active source rows silently absent from the extract
N_PHANTOM = 5            # extract rows whose user_id does not exist in source at all
N_DUPLICATE = 8          # active source rows duplicated (2x) in the extract
N_NULL_KEY = 1           # extract rows with user_id = NULL
N_EMAIL_MANGLED = 40      # active source rows present in extract, email case/whitespace altered only
N_STALE_ACTIVE = 12       # revoked source rows the extract still lists as status='active'

DEPARTMENTS = [
    "engineering", "finance", "sales", "support", "people-ops", "security", "legal",
]

FIRST_NAMES = [
    "alex", "bailey", "casey", "drew", "elliot", "frankie", "gray", "harper",
    "indigo", "jules", "kai", "logan", "morgan", "nico", "oakley", "parker",
    "quinn", "riley", "sam", "tatum", "uma", "val", "wren", "xan", "yael", "zeke",
]
LAST_NAMES = [
    "abara", "bosch", "chen", "diallo", "ekwueme", "farrow", "garza", "haas",
    "ibarra", "jansen", "kowalski", "leblanc", "mercer", "nakamura", "osei",
    "petit", "quiroga", "reyes", "sato", "thibault", "ueda", "vasquez",
    "wexler", "xiong", "yilmaz", "zabala",
]


@dataclass
class BuildResult:
    idp_source: list[dict]
    extract: list[dict]


def _make_email(first: str, last: str) -> str:
    return f"{first}.{last}@synthcorp.example"


def _synth_person(rng: random.Random) -> tuple[str, str, str]:
    first = rng.choice(FIRST_NAMES)
    last = rng.choice(LAST_NAMES)
    return first, last, _make_email(first, last)


def build(seed: int = SEED) -> BuildResult:
    """Build the source roster and the defective extract from a fixed seed."""
    rng = random.Random(seed)

    idp_source: list[dict] = []

    for i in range(1, N_ACTIVE + 1):
        first, last, email = _synth_person(rng)
        idp_source.append({
            "user_id": f"usr_{i:05d}",
            "email": email,
            "department": rng.choice(DEPARTMENTS),
            "status": "active",
            "revoked_at": None,
        })

    for i in range(N_ACTIVE + 1, N_ACTIVE + N_REVOKED + 1):
        first, last, email = _synth_person(rng)
        idp_source.append({
            "user_id": f"usr_{i:05d}",
            "email": email,
            "department": rng.choice(DEPARTMENTS),
            "status": "inactive",
            "revoked_at": f"2026-{rng.randint(1,8):02d}-{rng.randint(1,28):02d}",
        })

    active_rows = [r for r in idp_source if r["status"] == "active"]
    revoked_rows = [r for r in idp_source if r["status"] == "inactive"]

    rng.shuffle(active_rows)
    rng.shuffle(revoked_rows)

    missing_ids = {r["user_id"] for r in active_rows[:N_MISSING]}
    remaining_active = active_rows[N_MISSING:]

    dup_source_rows = remaining_active[:N_DUPLICATE]
    mangled_rows = remaining_active[N_DUPLICATE:N_DUPLICATE + N_EMAIL_MANGLED]
    clean_rows = remaining_active[N_DUPLICATE + N_EMAIL_MANGLED:]

    stale_active_rows = revoked_rows[:N_STALE_ACTIVE]

    extract: list[dict] = []

    def extract_row(src: dict, status: str) -> dict:
        return {
            "user_id": src["user_id"],
            "email": src["email"],
            "department": src["department"],
            "status": status,
            "extracted_at": "2026-08-31",
        }

    for r in clean_rows:
        extract.append(extract_row(r, "active"))

    for r in dup_source_rows:
        extract.append(extract_row(r, "active"))
        extract.append(extract_row(r, "active"))

    for r in mangled_rows:
        row = extract_row(r, "active")
        variant = rng.choice(["upper_domain", "leading_space", "trailing_space", "mixed_case"])
        local, domain = row["email"].split("@")
        if variant == "upper_domain":
            row["email"] = f"{local}@{domain.upper()}"
        elif variant == "leading_space":
            row["email"] = f"  {row['email']}"
        elif variant == "trailing_space":
            row["email"] = f"{row['email']}  "
        elif variant == "mixed_case":
            row["email"] = row["email"].upper()
        extract.append(row)

    for r in stale_active_rows:
        extract.append(extract_row(r, "active"))

    for i in range(N_PHANTOM):
        first, last, email = _synth_person(rng)
        extract.append({
            "user_id": f"usr_ghost_{i:03d}",
            "email": email,
            "department": rng.choice(DEPARTMENTS),
            "status": "active",
            "extracted_at": "2026-08-31",
        })

    for i in range(N_NULL_KEY):
        first, last, email = _synth_person(rng)
        extract.append({
            "user_id": None,
            "email": email,
            "department": rng.choice(DEPARTMENTS),
            "status": "active",
            "extracted_at": "2026-08-31",
        })

    rng.shuffle(extract)

    return BuildResult(idp_source=idp_source, extract=extract)


def load_into(con, seed: int = SEED) -> BuildResult:
    """Create idp_source and extract tables in the given DuckDB connection."""
    result = build(seed=seed)

    con.execute("""
        CREATE OR REPLACE TABLE idp_source (
            user_id     VARCHAR,
            email       VARCHAR,
            department  VARCHAR,
            status      VARCHAR,
            revoked_at  DATE
        )
    """)
    con.execute("""
        CREATE OR REPLACE TABLE extract (
            user_id      VARCHAR,
            email        VARCHAR,
            department   VARCHAR,
            status       VARCHAR,
            extracted_at DATE
        )
    """)

    con.executemany(
        "INSERT INTO idp_source VALUES (?, ?, ?, ?, ?)",
        [(r["user_id"], r["email"], r["department"], r["status"], r["revoked_at"]) for r in result.idp_source],
    )
    con.executemany(
        "INSERT INTO extract VALUES (?, ?, ?, ?, ?)",
        [(r["user_id"], r["email"], r["department"], r["status"], r["extracted_at"]) for r in result.extract],
    )

    return result


if __name__ == "__main__":
    import pathlib
    import duckdb

    here = pathlib.Path(__file__).parent
    db_path = here / "evidence.duckdb"
    db_path.unlink(missing_ok=True)

    con = duckdb.connect(str(db_path))
    result = load_into(con)

    con.execute(f"COPY idp_source TO '{here / 'idp_source.csv'}' (HEADER, DELIMITER ',')")
    con.execute(f"COPY extract TO '{here / 'extract.csv'}' (HEADER, DELIMITER ',')")
    con.close()

    print(f"built {db_path.name}: idp_source={len(result.idp_source)} rows, extract={len(result.extract)} rows")
    print(f"also wrote idp_source.csv and extract.csv alongside it")
