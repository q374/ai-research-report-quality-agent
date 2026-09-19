import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


from scripts.evidence_review_workflow import build_validation_record, submit_review
from scripts.render_evidence_review_prototype import render_review_page


FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / f"{name}.json").read_text(encoding="utf-8"))


def record_for(name: str, *, label: str | None = None) -> dict:
    record = build_validation_record(
        load_fixture(name),
        thread_id=f"thread-{name}",
        run_id=f"run-{name}",
        message_id=f"message-{name}",
        owner_user_id="reviewer-1",
        now="2026-09-19T10:00:00+08:00",
    )
    record["prototype_label"] = label or name
    return record


class ReviewPageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.buttons = []
        self.text_parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "button":
            self.buttons.append(dict(attrs))

    def handle_data(self, data):
        if data.strip():
            self.text_parts.append(data.strip())

    @property
    def text(self):
        return " ".join(self.text_parts)


class EvidenceReviewPrototypeTests(unittest.TestCase):
    def test_blocked_card_disables_approval(self):
        html = render_review_page([record_for("t001_v3", label="阻断示例")])
        parser = ReviewPageParser()
        parser.feed(html)

        approve = next(button for button in parser.buttons if button.get("data-action") == "approve")
        self.assertIn("disabled", approve)
        self.assertIn("不可发布", parser.text)
        self.assertIn("877 / 800 字符", parser.text)

    def test_review_required_card_allows_approval(self):
        html = render_review_page([record_for("b0_clean_current", label="待复核示例")])
        parser = ReviewPageParser()
        parser.feed(html)

        approve = next(button for button in parser.buttons if button.get("data-action") == "approve")
        self.assertNotIn("disabled", approve)
        self.assertIn("待人工复核", parser.text)

    def test_confirmed_card_shows_reviewer_and_time(self):
        pending = record_for("b0_clean_current", label="已确认示例")
        confirmed = submit_review(
            pending,
            actor_user_id="reviewer-1",
            decision="approved",
            expected_report_hash=pending["report_hash"],
            idempotency_key="prototype-approved",
            now="2026-09-19T10:03:00+08:00",
        )
        confirmed["prototype_label"] = "已确认示例"
        html = render_review_page([confirmed])
        parser = ReviewPageParser()
        parser.feed(html)

        self.assertIn("已确认", parser.text)
        self.assertIn("reviewer-1", parser.text)
        self.assertIn("2026-09-19T10:03:00+08:00", parser.text)

    def test_validator_error_disables_approval_and_hides_exception(self):
        def broken_validator(_payload):
            raise RuntimeError("secret internal trace")

        record = build_validation_record(
            load_fixture("b0_clean_current"),
            thread_id="thread-error",
            run_id="run-error",
            message_id="message-error",
            owner_user_id="reviewer-1",
            validator_func=broken_validator,
            now="2026-09-19T10:00:00+08:00",
        )
        record["prototype_label"] = "异常示例"
        html = render_review_page([record])
        parser = ReviewPageParser()
        parser.feed(html)

        approve = next(button for button in parser.buttons if button.get("data-action") == "approve")
        self.assertIn("disabled", approve)
        self.assertIn("校验异常", parser.text)
        self.assertNotIn("secret internal trace", html)

    def test_drawer_contains_four_review_sections(self):
        html = render_review_page([record_for("t001_v3")])
        parser = ReviewPageParser()
        parser.feed(html)

        for heading in ("报告陈述", "证据原文", "校验发现", "人工动作"):
            self.assertIn(heading, parser.text)

    def test_prototype_is_local_only_and_contains_no_secret_pattern(self):
        html = render_review_page(
            [record_for("t001_v3"), record_for("b0_clean_current")]
        )

        self.assertIn("静态原型，不会写入 DeerFlow", html)
        self.assertNotIn("fetch(", html)
        self.assertNotIn("XMLHttpRequest", html)
        self.assertIsNone(re.search(r"sk-[A-Za-z0-9]{16,}", html))


if __name__ == "__main__":
    unittest.main()
