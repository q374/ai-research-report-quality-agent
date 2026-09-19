import copy
import importlib.util
import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "evidence_validator.py"
FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def load_module():
    spec = importlib.util.spec_from_file_location("evidence_validator", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载 evidence_validator.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))


class EvidenceValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_module()

    def test_known_badcases_are_blocked(self):
        cases = {
            "t001_v1": {"EV-01", "EV-03", "EV-04", "EV-06"},
            "t001_v2": {"EV-04", "EV-08"},
            "t001_v3": {"EV-03", "EV-06"},
        }

        for name, expected_blockers in cases.items():
            with self.subTest(name=name):
                result = self.validator.validate(load_fixture(name))
                blocker_rules = {
                    finding["rule_id"]
                    for finding in result["findings"]
                    if finding["severity"] == "blocker"
                }
                self.assertEqual("blocked", result["status"])
                self.assertEqual(expected_blockers, blocker_rules)

    def test_visible_character_counts_are_calculated_from_text(self):
        expected = {"t001_v1": 1217, "t001_v2": 575, "t001_v3": 877}
        for name, length in expected.items():
            with self.subTest(name=name):
                result = self.validator.validate(load_fixture(name))
                self.assertEqual(length, result["metrics"]["actual_chars"])

    def test_v3_duplicate_sources_are_normalized(self):
        result = self.validator.validate(load_fixture("t001_v3"))
        warning_rules = {
            finding["rule_id"]
            for finding in result["findings"]
            if finding["severity"] == "warning"
        }
        self.assertIn("EV-07", warning_rules)
        self.assertEqual(4, result["metrics"]["page_views"])
        self.assertEqual(2, result["metrics"]["unique_pages"])

    def test_clean_report_still_requires_human_approval(self):
        payload = {
            "brief": {
                "task_id": "clean-sample",
                "required_dimensions": ["capability", "model_quality_limit"],
                "allowed_domains": ["openai.com"],
                "time_scope": "as_of_access_date",
                "max_searches": 2,
                "max_pages": 2,
                "max_chars": 800,
                "forbidden_tools": ["subagent", "file_generation"],
            },
            "claims": [
                {
                    "claim_id": "c1",
                    "text": "发布时可生成带来源的研究报告。",
                    "claim_type": "historical_fact",
                    "dimension": "capability",
                    "evidence_ids": ["e1"],
                    "citation_evidence_ids": ["e1"],
                    "is_key": True,
                },
                {
                    "claim_id": "c2",
                    "text": "发布页披露了幻觉和错误推断风险。",
                    "claim_type": "historical_fact",
                    "dimension": "model_quality_limit",
                    "evidence_ids": ["e2"],
                    "citation_evidence_ids": ["e2"],
                    "is_key": True,
                },
            ],
            "evidence": [
                {
                    "evidence_id": "e1",
                    "source_url": "https://openai.com/index/introducing-deep-research/",
                    "canonical_url": "https://openai.com/index/introducing-deep-research/",
                    "title": "Introducing deep research",
                    "published_at": "2025-02-02",
                    "accessed_at": "2026-09-19",
                    "excerpt": "create a comprehensive report",
                    "status": "confirmed",
                },
                {
                    "evidence_id": "e2",
                    "source_url": "https://openai.com/index/introducing-deep-research/#limitations",
                    "canonical_url": "https://openai.com/index/introducing-deep-research/",
                    "title": "Introducing deep research - Limitations",
                    "published_at": "2025-02-02",
                    "accessed_at": "2026-09-19",
                    "excerpt": "hallucinate facts or make incorrect inferences",
                    "status": "confirmed",
                },
            ],
            "report": {
                "report_id": "clean-sample",
                "rendered_text": "发布时可生成带来源的研究报告。发布页披露了幻觉和错误推断风险。",
                "observed_searches": 1,
                "observed_page_urls": ["https://openai.com/index/introducing-deep-research/"],
                "used_tools": ["web_search", "web_fetch"],
                "token_usage": {"input": 100, "output": 20},
                "latency_seconds": 1,
            },
            "audit": {
                "model": "offline-fixture",
                "prompt_version": "test",
                "accessed_at": "2026-09-19",
                "cost_estimate_cny": 0,
                "human_review": "pending",
            },
        }

        pending = self.validator.validate(payload)
        self.assertEqual("review_required", pending["status"])
        approved_payload = copy.deepcopy(payload)
        approved_payload["audit"]["human_review"] = "approved"
        approved = self.validator.validate(approved_payload)
        self.assertEqual("confirmed", approved["status"])

    def test_missing_contract_fails_closed(self):
        result = self.validator.validate({"brief": {"task_id": "broken"}})
        self.assertEqual("blocked", result["status"])
        self.assertIn(
            "EV-10",
            {finding["rule_id"] for finding in result["findings"]},
        )

    def test_every_finding_is_actionable(self):
        for name in ("t001_v1", "t001_v2", "t001_v3"):
            with self.subTest(name=name):
                for finding in self.validator.validate(load_fixture(name))["findings"]:
                    self.assertTrue(finding["rule_id"])
                    self.assertIn(finding["severity"], {"blocker", "warning", "info"})
                    self.assertTrue(finding["message"])
                    self.assertTrue(finding["required_action"])

    def test_other_rule_families_fail_closed(self):
        cases = []

        missing_binding = load_fixture("t001_v3")
        missing_binding["claims"][0]["evidence_ids"] = ["missing-evidence"]
        missing_binding["claims"][0]["citation_evidence_ids"] = ["missing-evidence"]
        cases.append(("missing_binding", missing_binding, "EV-02"))

        missing_citation = load_fixture("t001_v2")
        missing_citation["claims"][0]["citation_evidence_ids"] = []
        cases.append(("missing_citation", missing_citation, "EV-05"))

        conflicting_evidence = load_fixture("t001_v2")
        conflicting_evidence["evidence"][0]["status"] = "conflict"
        cases.append(("conflicting_evidence", conflicting_evidence, "EV-09"))

        disallowed_domain = load_fixture("t001_v2")
        disallowed_domain["evidence"][0]["source_url"] = "https://example.com/unsupported"
        disallowed_domain["evidence"][0]["canonical_url"] = "https://example.com/unsupported"
        cases.append(("disallowed_domain", disallowed_domain, "EV-06"))

        for name, payload, expected_rule in cases:
            with self.subTest(name=name):
                result = self.validator.validate(payload)
                blocker_rules = {
                    finding["rule_id"]
                    for finding in result["findings"]
                    if finding["severity"] == "blocker"
                }
                self.assertEqual("blocked", result["status"])
                self.assertIn(expected_rule, blocker_rules)


if __name__ == "__main__":
    unittest.main()
