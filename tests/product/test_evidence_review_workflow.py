import copy
import json
import unittest
from pathlib import Path


from scripts.evidence_review_workflow import (
    build_validation_record,
    refresh_validation_record,
    submit_review,
)


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))


def clean_payload() -> dict:
    payload = load_fixture("t001_v3")
    payload["report"]["rendered_text"] = (
        "当前帮助页说明 Deep Research 可规划并综合复杂问题。"
        "历史发布页披露了幻觉、错误推断和置信度校准风险。"
    )
    payload["report"].pop("self_reported_chars", None)
    payload["claims"][-1]["text"] = "历史发布页披露了幻觉、错误推断和置信度校准风险。"
    payload["claims"][-1]["claim_type"] = "historical_fact"
    payload["report"]["observed_page_urls"] = [
        "https://help.openai.com/en/articles/10500283-deep-research-in-chatgpt",
        "https://openai.com/index/introducing-deep-research/",
    ]
    return payload


def build_clean_record() -> dict:
    return build_validation_record(
        clean_payload(),
        thread_id="thread-1",
        run_id="run-1",
        message_id="message-1",
        owner_user_id="user-1",
        now="2026-09-19T10:00:00+08:00",
    )


class EvidenceReviewWorkflowTests(unittest.TestCase):
    def test_record_binds_identity_and_system_validation(self):
        record = build_clean_record()

        self.assertEqual("thread-1", record["thread_id"])
        self.assertEqual("run-1", record["run_id"])
        self.assertEqual("message-1", record["message_id"])
        self.assertEqual("user-1", record["owner_user_id"])
        self.assertEqual("review_required", record["auto_status"])
        self.assertEqual("review_required", record["final_status"])
        self.assertEqual([], record["review_decisions"])
        self.assertEqual(
            len(clean_payload()["report"]["rendered_text"]),
            record["validation_result"]["metrics"]["actual_chars"],
        )

    def test_report_hash_changes_when_text_or_evidence_changes(self):
        original_payload = clean_payload()
        original = build_validation_record(
            original_payload,
            thread_id="thread-1",
            run_id="run-1",
            message_id="message-1",
            owner_user_id="user-1",
            now="2026-09-19T10:00:00+08:00",
        )

        text_changed = copy.deepcopy(original_payload)
        text_changed["report"]["rendered_text"] += "更新。"
        text_record = refresh_validation_record(
            original,
            text_changed,
            now="2026-09-19T10:01:00+08:00",
        )

        evidence_changed = copy.deepcopy(original_payload)
        evidence_changed["evidence"][0]["excerpt"] += " changed"
        evidence_record = refresh_validation_record(
            original,
            evidence_changed,
            now="2026-09-19T10:02:00+08:00",
        )

        self.assertNotEqual(original["report_hash"], text_record["report_hash"])
        self.assertNotEqual(original["report_hash"], evidence_record["report_hash"])
        self.assertEqual([], text_record["review_decisions"])
        self.assertEqual("review_required", text_record["final_status"])

    def test_validator_exception_fails_closed(self):
        def broken_validator(_payload):
            raise RuntimeError("simulated validator outage")

        record = build_validation_record(
            clean_payload(),
            thread_id="thread-1",
            run_id="run-1",
            message_id="message-1",
            owner_user_id="user-1",
            validator_func=broken_validator,
            now="2026-09-19T10:00:00+08:00",
        )

        self.assertEqual("validator_error", record["auto_status"])
        self.assertEqual("validator_error", record["final_status"])
        self.assertEqual("EV-10", record["validation_result"]["findings"][0]["rule_id"])
        self.assertNotIn("simulated validator outage", json.dumps(record, ensure_ascii=False))

    def test_non_owner_cannot_review(self):
        record = build_clean_record()

        with self.assertRaises(PermissionError):
            submit_review(
                record,
                actor_user_id="user-2",
                decision="approved",
                expected_report_hash=record["report_hash"],
                idempotency_key="review-1",
                now="2026-09-19T10:03:00+08:00",
            )

        self.assertEqual([], record["review_decisions"])

    def test_blocked_or_error_record_cannot_be_approved(self):
        blocked = build_validation_record(
            load_fixture("t001_v3"),
            thread_id="thread-1",
            run_id="run-1",
            message_id="message-1",
            owner_user_id="user-1",
            now="2026-09-19T10:00:00+08:00",
        )

        with self.assertRaises(ValueError):
            submit_review(
                blocked,
                actor_user_id="user-1",
                decision="approved",
                expected_report_hash=blocked["report_hash"],
                idempotency_key="review-blocked",
                now="2026-09-19T10:03:00+08:00",
            )

    def test_returned_and_rejected_require_reason(self):
        for decision in ("returned", "rejected"):
            with self.subTest(decision=decision):
                record = build_clean_record()
                with self.assertRaises(ValueError):
                    submit_review(
                        record,
                        actor_user_id="user-1",
                        decision=decision,
                        reason=" ",
                        expected_report_hash=record["report_hash"],
                        idempotency_key=f"review-{decision}",
                        now="2026-09-19T10:03:00+08:00",
                    )

    def test_valid_approval_records_reviewer_hash_and_time(self):
        record = build_clean_record()
        approved = submit_review(
            record,
            actor_user_id="user-1",
            decision="approved",
            expected_report_hash=record["report_hash"],
            idempotency_key="review-approve",
            now="2026-09-19T10:03:00+08:00",
        )

        self.assertEqual("confirmed", approved["final_status"])
        self.assertEqual(1, len(approved["review_decisions"]))
        decision = approved["review_decisions"][0]
        self.assertEqual("user-1", decision["reviewer_user_id"])
        self.assertEqual(record["report_hash"], decision["report_hash"])
        self.assertEqual("2026-09-19T10:03:00+08:00", decision["created_at"])
        self.assertEqual([], record["review_decisions"])

    def test_stale_hash_is_rejected(self):
        record = build_clean_record()

        with self.assertRaises(ValueError):
            submit_review(
                record,
                actor_user_id="user-1",
                decision="approved",
                expected_report_hash="stale-hash",
                idempotency_key="review-stale",
                now="2026-09-19T10:03:00+08:00",
            )

    def test_idempotency_key_does_not_append_duplicate_decision(self):
        record = build_clean_record()
        first = submit_review(
            record,
            actor_user_id="user-1",
            decision="approved",
            expected_report_hash=record["report_hash"],
            idempotency_key="same-key",
            now="2026-09-19T10:03:00+08:00",
        )
        second = submit_review(
            first,
            actor_user_id="user-1",
            decision="approved",
            expected_report_hash=record["report_hash"],
            idempotency_key="same-key",
            now="2026-09-19T10:04:00+08:00",
        )

        self.assertEqual(1, len(second["review_decisions"]))
        self.assertEqual(
            first["review_decisions"][0]["decision_id"],
            second["review_decisions"][0]["decision_id"],
        )


if __name__ == "__main__":
    unittest.main()
