"""Shared helpers for shelling out to the opa binary from pytest."""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

REGO_DIR = pathlib.Path(__file__).parent.parent / "rego"
MUTANTS_DIR = pathlib.Path(__file__).parent.parent / "mutants"

OPA_AVAILABLE = shutil.which("opa") is not None


def eval_allow_autonomous(policy_path: pathlib.Path, risk_flag: str, confidence: str, reversibility: str, approval_evidence: str) -> bool:
    """Evaluate data.autonomy_gate.allow_autonomous against one input via `opa eval`."""
    input_doc = {
        "risk_flag": risk_flag,
        "confidence": confidence,
        "reversibility": reversibility,
        "approval_evidence": approval_evidence,
    }
    result = subprocess.run(
        ["opa", "eval", "-f", "raw", "-d", str(policy_path), "-I", "data.autonomy_gate.allow_autonomous"],
        input=json.dumps(input_doc),
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"opa eval failed for {input_doc}: {result.stderr}")
    value = result.stdout.strip()
    if value not in ("true", "false"):
        raise RuntimeError(f"unexpected opa eval output for {input_doc}: {value!r}")
    return value == "true"


def run_opa_test(*rego_files: pathlib.Path) -> subprocess.CompletedProcess:
    """Run `opa test` over the given rego files and return the completed process."""
    return subprocess.run(
        ["opa", "test", *(str(f) for f in rego_files)],
        capture_output=True,
        text=True,
        timeout=30,
    )
