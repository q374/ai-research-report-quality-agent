import { beforeEach, describe, expect, test, rs } from "@rstest/core";

rs.mock("@/core/api/fetcher", () => ({
  fetch: rs.fn(),
}));

rs.mock("@/core/config", () => ({
  getBackendBaseURL: () => "/backend",
}));

import { getEvidenceValidation } from "@/core/api/evidence-validation";
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
        auto_status: "blocked",
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
    });
  });

  test("returns null when the run has no validation record", async () => {
    mockedFetch.mockResolvedValueOnce(jsonResponse(404, { detail: "not found" }));
    await expect(getEvidenceValidation("thread-1", "run-1")).resolves.toBeNull();
  });
});
