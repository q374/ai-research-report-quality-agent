import { beforeEach, describe, expect, test, rs } from "@rstest/core";

rs.mock("@/core/api/fetcher", () => ({
  fetch: rs.fn(),
}));

rs.mock("@/core/config", () => ({
  getBackendBaseURL: () => "/backend",
}));

import {
  getEvidenceValidation,
  submitEvidenceReview,
} from "@/core/api/evidence-validation";
import { fetch as fetcher } from "@/core/api/fetcher";

const mockedFetch = rs.mocked(fetcher);

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  mockedFetch.mockReset();
});

describe("getEvidenceValidation", () => {
  test("normalizes the backend validation_result envelope for the UI", async () => {
    mockedFetch.mockResolvedValueOnce(
      jsonResponse(200, {
        validation_id: "v1",
        report_hash: "hash-1",
        auto_status: "blocked",
        final_status: "blocked",
        review_decisions: [],
        validation_result: {
          status: "blocked",
          finding_counts: { blocker: 2, warning: 1, info: 0 },
          findings: [
            {
              rule_id: "EV-05",
              severity: "blocker",
              message: "引用与证据不一致。",
              required_action: "修正引用。",
            },
          ],
          metrics: { actual_chars: 1079, searches: 6 },
        },
      }),
    );

    await expect(getEvidenceValidation("thread-1", "run-1")).resolves.toEqual({
      validation_id: "v1",
      report_hash: "hash-1",
      status: "blocked",
      final_status: "blocked",
      review_decisions: [],
      finding_counts: { blocker: 2, warning: 1, info: 0 },
      findings: [
        {
          rule_id: "EV-05",
          severity: "blocker",
          message: "引用与证据不一致。",
          required_action: "修正引用。",
        },
      ],
      metrics: { actual_chars: 1079, searches: 6 },
    });
  });

  test("returns null when the run has no validation record", async () => {
    mockedFetch.mockResolvedValueOnce(jsonResponse(404, { detail: "not found" }));
    await expect(getEvidenceValidation("thread-1", "run-1")).resolves.toBeNull();
  });

  test("prefers the persisted manual final status", async () => {
    mockedFetch.mockResolvedValueOnce(
      jsonResponse(200, {
        validation_id: "v1",
        report_hash: "hash-1",
        final_status: "confirmed",
        review_decisions: [{ decision: "approved" }],
        validation_result: {
          status: "review_required",
          finding_counts: { blocker: 0, warning: 0, info: 0 },
        },
      }),
    );

    await expect(getEvidenceValidation("thread-1", "run-1")).resolves.toMatchObject({
      validation_id: "v1",
      report_hash: "hash-1",
      status: "confirmed",
      final_status: "confirmed",
      review_decisions: [{ decision: "approved" }],
    });
  });
});

describe("submitEvidenceReview", () => {
  test("submits an approval bound to the current report hash", async () => {
    mockedFetch.mockResolvedValueOnce(
      jsonResponse(200, {
        validation_id: "v1",
        report_hash: "hash-1",
        final_status: "confirmed",
        review_decisions: [{ decision: "approved" }],
        validation_result: {
          status: "confirmed",
          finding_counts: { blocker: 0, warning: 0, info: 0 },
        },
      }),
    );

    await expect(
      submitEvidenceReview("thread-1", "run-1", {
        decision: "approved",
        expected_report_hash: "hash-1",
        idempotency_key: "review-1",
      }),
    ).resolves.toMatchObject({ status: "confirmed" });

    expect(mockedFetch).toHaveBeenCalledWith(
      "/backend/api/threads/thread-1/runs/run-1/evidence-validation/reviews",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          decision: "approved",
          expected_report_hash: "hash-1",
          idempotency_key: "review-1",
        }),
      }),
    );
  });
});
