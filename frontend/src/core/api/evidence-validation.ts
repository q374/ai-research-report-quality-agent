import { getBackendBaseURL } from "../config";

import { fetch } from "./fetcher";

export interface EvidenceValidationFinding {
  rule_id: string;
  severity: "blocker" | "warning" | "info" | string;
  message: string;
  required_action?: string;
}

export interface EvidenceValidationRecord {
  status: "blocked" | "review_required" | "confirmed" | "rejected" | string;
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
  return response.json();
}
