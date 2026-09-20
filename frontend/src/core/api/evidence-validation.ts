import { getBackendBaseURL } from "../config";

import { fetch } from "./fetcher";

export interface EvidenceValidationFinding {
  rule_id: string;
  severity: "blocker" | "warning" | "info" | string;
  message: string;
  required_action?: string;
}

export interface EvidenceValidationRecord {
  validation_id?: string;
  run_id?: string;
  report_hash?: string;
  status: "blocked" | "review_required" | "confirmed" | "rejected" | string;
  final_status?: string;
  review_decisions?: Array<{
    decision?: string;
    reason?: string;
    reviewer_user_id?: string;
    created_at?: string;
  }>;
  finding_counts?: {
    blocker?: number;
    warning?: number;
    info?: number;
  };
  findings?: EvidenceValidationFinding[];
  metrics?: {
    actual_chars?: number;
    page_views?: number;
    unique_pages?: number;
    searches?: number;
  };
}

export type EvidenceReviewDecision = "approved" | "returned" | "rejected";

export interface EvidenceReviewRequest {
  decision: EvidenceReviewDecision;
  expected_report_hash: string;
  idempotency_key: string;
  reason?: string;
}

export function buildEvidenceReviewIdempotencyKey(
  validationId: string,
  decision: EvidenceReviewDecision,
): string {
  return `evidence-review:${validationId}:${decision}`;
}

interface EvidenceValidationEnvelope {
  validation_id?: string;
  report_hash?: string;
  auto_status?: string;
  final_status?: string;
  review_decisions?: EvidenceValidationRecord["review_decisions"];
  validation_result?: EvidenceValidationRecord;
  status?: string;
}

function normalizeEvidenceValidation(
  body: EvidenceValidationEnvelope,
): EvidenceValidationRecord {
  if (
    body.validation_result &&
    typeof body.validation_result.status === "string"
  ) {
    return {
      ...body.validation_result,
      validation_id: body.validation_id,
      report_hash: body.report_hash,
      status: body.final_status ?? body.validation_result.status,
      final_status: body.final_status,
      review_decisions: body.review_decisions ?? [],
    };
  }
  if (typeof body.status === "string") {
    return body as EvidenceValidationRecord;
  }
  throw new Error("Evidence validation response is missing validation_result");
}

export async function getEvidenceValidation(
  threadId: string,
  runId: string,
): Promise<EvidenceValidationRecord | null> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/runs/${encodeURIComponent(runId)}/evidence-validation`,
  );
  if (response.status === 404) return null;
  if (!response.ok) {
    throw new Error(`Failed to load evidence validation: ${response.status}`);
  }
  return normalizeEvidenceValidation(
    (await response.json()) as EvidenceValidationEnvelope,
  );
}

export async function submitEvidenceReview(
  threadId: string,
  runId: string,
  request: EvidenceReviewRequest,
): Promise<EvidenceValidationRecord> {
  const response = await fetch(
    `${getBackendBaseURL()}/api/threads/${encodeURIComponent(threadId)}/runs/${encodeURIComponent(runId)}/evidence-validation/reviews`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    },
  );
  if (!response.ok) {
    let detail: string | undefined;
    try {
      const errorBody = (await response.json()) as { detail?: unknown };
      if (typeof errorBody.detail === "string") detail = errorBody.detail;
    } catch {
      // 非 JSON 错误响应回退为状态码。
    }
    throw new Error(detail ?? `人工复核提交失败：${response.status}`);
  }
  return normalizeEvidenceValidation(
    (await response.json()) as EvidenceValidationEnvelope,
  );
}
