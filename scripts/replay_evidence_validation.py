#!/usr/bin/env python3
"""按清单离线回放证据校验样本并核对字面期望。"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.evidence_review_workflow import build_validation_record


def _resolve_fixture(manifest_path: Path, fixture: str) -> Path:
    path = Path(fixture)
    if path.is_absolute():
        return path
    return manifest_path.parent / path


def replay_manifest(manifest_path: Path) -> dict:
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sample_specs = manifest.get("samples")
    if not isinstance(sample_specs, list):
        raise ValueError("manifest.samples 必须是数组")

    results = []
    status_counts: Counter[str] = Counter()
    false_releases = 0
    false_blocks = 0
    mismatches = 0

    for index, spec in enumerate(sample_specs):
        sample_id = str(spec["id"])
        fixture_path = _resolve_fixture(manifest_path, str(spec["fixture"]))
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        record = build_validation_record(
            payload,
            thread_id=f"offline-thread-{index + 1}",
            run_id=f"offline-run-{index + 1}",
            message_id=f"offline-message-{index + 1}",
            owner_user_id="offline-reviewer",
            now="2026-09-19T00:00:00+08:00",
        )
        validation = record["validation_result"]
        actual_status = record["auto_status"]
        blockers = sorted(
            {
                finding["rule_id"]
                for finding in validation.get("findings", [])
                if finding.get("severity") == "blocker"
            }
        )
        warnings = sorted(
            {
                finding["rule_id"]
                for finding in validation.get("findings", [])
                if finding.get("severity") == "warning"
            }
        )
        expected_status = str(spec["expected_status"])
        expected_blockers = sorted(set(spec.get("expected_blockers", [])))
        status_matches = actual_status == expected_status
        blockers_match = blockers == expected_blockers
        matches_expected = status_matches and blockers_match

        if expected_status == "blocked" and actual_status != "blocked":
            false_releases += 1
        if expected_status != "blocked" and actual_status == "blocked":
            false_blocks += 1
        if not matches_expected:
            mismatches += 1

        status_counts[actual_status] += 1
        results.append(
            {
                "id": sample_id,
                "fixture": fixture_path.name,
                "expected_status": expected_status,
                "actual_status": actual_status,
                "expected_blockers": expected_blockers,
                "blockers": blockers,
                "warnings": warnings,
                "metrics": validation.get("metrics", {}),
                "report_hash": record["report_hash"],
                "matches_expected": matches_expected,
            }
        )

    return {
        "manifest_version": manifest.get("manifest_version"),
        "summary": {
            "total": len(results),
            "blocked": status_counts["blocked"],
            "review_required": status_counts["review_required"],
            "confirmed": status_counts["confirmed"],
            "validator_error": status_counts["validator_error"],
            "false_releases": false_releases,
            "false_blocks": false_blocks,
            "mismatches": mismatches,
        },
        "samples": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="离线回放证据校验样本")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    replay = replay_manifest(args.manifest)
    text = json.dumps(replay, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")

    summary = replay["summary"]
    print(
        f"{summary['total']} samples, "
        f"false_releases={summary['false_releases']}, "
        f"false_blocks={summary['false_blocks']}, "
        f"mismatches={summary['mismatches']}"
    )
    return 1 if summary["mismatches"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
