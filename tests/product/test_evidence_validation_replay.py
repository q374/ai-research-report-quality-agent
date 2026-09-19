import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


from scripts.replay_evidence_validation import replay_manifest


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
MANIFEST = FIXTURE_DIR / "b0_manifest.json"


class EvidenceValidationReplayTests(unittest.TestCase):
    def test_manifest_replays_three_blocked_and_five_reviewable_samples(self):
        replay = replay_manifest(MANIFEST)

        self.assertEqual(8, replay["summary"]["total"])
        self.assertEqual(3, replay["summary"]["blocked"])
        self.assertEqual(5, replay["summary"]["review_required"])
        self.assertEqual(0, replay["summary"]["false_releases"])
        self.assertEqual(0, replay["summary"]["false_blocks"])
        self.assertEqual(0, replay["summary"]["mismatches"])

    def test_boundary_metrics_use_system_calculation(self):
        replay = replay_manifest(MANIFEST)
        by_id = {item["id"]: item for item in replay["samples"]}

        self.assertEqual(800, by_id["b0_exact_limit"]["metrics"]["actual_chars"])
        self.assertEqual("review_required", by_id["b0_exact_limit"]["actual_status"])
        self.assertEqual(2, by_id["b0_duplicate_urls"]["metrics"]["page_views"])
        self.assertEqual(1, by_id["b0_duplicate_urls"]["metrics"]["unique_pages"])
        self.assertIn("EV-07", by_id["b0_duplicate_urls"]["warnings"])

    def test_expected_blocker_sets_match_literal_manifest(self):
        replay = replay_manifest(MANIFEST)
        by_id = {item["id"]: item for item in replay["samples"]}

        self.assertEqual(
            ["EV-01", "EV-03", "EV-04", "EV-06"],
            by_id["t001_v1"]["blockers"],
        )
        self.assertEqual(["EV-04", "EV-08"], by_id["t001_v2"]["blockers"])
        self.assertEqual(["EV-03", "EV-06"], by_id["t001_v3"]["blockers"])

    def test_positive_fixture_claims_are_visible_in_rendered_report(self):
        positive_names = (
            "b0_clean_current",
            "b0_clean_historical",
            "b0_exact_limit",
            "b0_duplicate_urls",
            "b0_neutral_review",
        )
        for name in positive_names:
            with self.subTest(name=name):
                payload = json.loads(
                    (FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8")
                )
                rendered_text = payload["report"]["rendered_text"]
                for claim in payload["claims"]:
                    self.assertIn(claim["text"], rendered_text)

    def test_cli_returns_nonzero_when_expectation_is_wrong(self):
        bad_manifest = {
            "manifest_version": "1.0",
            "samples": [
                {
                    "id": "known-bad",
                    "fixture": str(FIXTURE_DIR / "t001_v3.json"),
                    "expected_status": "review_required",
                    "expected_blockers": [],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            output_path = Path(temp_dir) / "result.json"
            manifest_path.write_text(
                json.dumps(bad_manifest, ensure_ascii=False), encoding="utf-8"
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "replay_evidence_validation.py"),
                    str(manifest_path),
                    "--output",
                    str(output_path),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(1, completed.returncode)
        self.assertIn("mismatches=1", completed.stdout)


if __name__ == "__main__":
    unittest.main()
