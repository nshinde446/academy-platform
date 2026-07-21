#!/usr/bin/env python3
"""Assert that live GitHub repo config matches .github/config-spec.json.

Exits non-zero on any drift, so a CI job that runs this fails when the repo's
real branch protection or environment gates diverge from what the spec (and the
docs that reference it) claim.

Why this exists: a control described only in prose is indistinguishable from a
control that does not exist. This is the check that catches the divergence
instead of leaving it to be discovered by accident. See
docs/delivery-workflow-architecture.md.

Reads config via the `gh` CLI, which the workflow authenticates with a token
granted `administration: read` (needed to read branch protection). Only keys
present in the spec are asserted; anything the spec does not mention is ignored,
so repo settings and integration-managed environments (Vercel's Preview /
Production) never trigger a false alarm.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO = "nshinde446/academy-platform"
SPEC_PATH = Path(__file__).resolve().parents[1] / "config-spec.json"


class DriftError(Exception):
    """A single mismatch between spec and live config."""


def _strip_comments(value: Any) -> Any:
    """Drop the documentation-only ``$comment`` / ``$*`` keys from the spec."""
    if isinstance(value, dict):
        return {
            k: _strip_comments(v)
            for k, v in value.items()
            if not k.startswith("$")
        }
    if isinstance(value, list):
        return [_strip_comments(v) for v in value]
    return value


def _gh_api(path: str) -> Any:
    """Call `gh api <path>`; return parsed JSON, or None on a 404."""
    result = subprocess.run(
        ["gh", "api", path],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        if "Not Found" in stderr or "HTTP 404" in stderr:
            return None
        # A 403 here almost always means the token lacks administration:read.
        # Treat inability to VERIFY as failure — a check that silently can't
        # see the config is exactly the blind spot this job exists to remove.
        raise DriftError(
            f"could not read `{path}` (is the workflow token granted "
            f"administration: read?):\n{stderr}"
        )
    return json.loads(result.stdout)


def check_branch_protection(spec: dict[str, Any], drifts: list[str]) -> None:
    for branch, want in spec.items():
        live = _gh_api(f"repos/{REPO}/branches/{branch}/protection")
        if live is None:
            drifts.append(
                f"branch `{branch}`: expected protection, but the branch has "
                f"NONE (or does not exist)"
            )
            continue

        want_checks = want.get("required_status_checks")
        if want_checks is not None:
            live_checks = live.get("required_status_checks") or {}
            if bool(want_checks.get("strict")) != bool(live_checks.get("strict")):
                drifts.append(
                    f"branch `{branch}`: required_status_checks.strict = "
                    f"{live_checks.get('strict')!r}, spec wants "
                    f"{want_checks.get('strict')!r}"
                )
            want_ctx = set(want_checks.get("contexts", []))
            live_ctx = set(live_checks.get("contexts", []))
            if want_ctx - live_ctx:
                drifts.append(
                    f"branch `{branch}`: required checks MISSING "
                    f"{sorted(want_ctx - live_ctx)} (live: {sorted(live_ctx)})"
                )

        for key in ("allow_force_pushes", "allow_deletions"):
            if key in want:
                live_val = bool((live.get(key) or {}).get("enabled"))
                if live_val != bool(want[key]):
                    drifts.append(
                        f"branch `{branch}`: {key} = {live_val}, spec wants "
                        f"{want[key]}"
                    )


def check_environments(spec: dict[str, Any], drifts: list[str]) -> None:
    for env, want in spec.items():
        live = _gh_api(f"repos/{REPO}/environments/{env}")
        if live is None:
            drifts.append(
                f"environment `{env}`: does not exist. NOTE: GitHub silently "
                f"auto-creates an UNPROTECTED environment when a workflow names "
                f"an unknown one — create this deliberately with its intended "
                f"rules."
            )
            continue

        rule_types = {r.get("type") for r in live.get("protection_rules", [])}
        if "required_reviewers" in want:
            has_reviewers = "required_reviewers" in rule_types
            if has_reviewers != bool(want["required_reviewers"]):
                if want["required_reviewers"]:
                    drifts.append(
                        f"environment `{env}`: expected a required-reviewer "
                        f"gate, but it has NONE. This is the exact failure this "
                        f"job guards against."
                    )
                else:
                    drifts.append(
                        f"environment `{env}`: has a required-reviewer gate, "
                        f"but the spec says it must ship unattended. Gate "
                        f"migrations via `production-migrations` instead."
                    )


def main() -> int:
    spec = _strip_comments(json.loads(SPEC_PATH.read_text(encoding="utf-8")))
    drifts: list[str] = []

    try:
        check_branch_protection(spec.get("branch_protection", {}), drifts)
        check_environments(spec.get("environments", {}), drifts)
    except DriftError as exc:
        print(f"::error::config-drift check could not run: {exc}")
        return 2

    if drifts:
        print("::error::Repository config has DRIFTED from .github/config-spec.json:")
        for d in drifts:
            print(f"  - {d}")
        print(
            "\nEither fix the live config on GitHub, or update config-spec.json "
            "if the change was intended (in the same PR)."
        )
        return 1

    print("Repository config matches .github/config-spec.json. No drift.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
