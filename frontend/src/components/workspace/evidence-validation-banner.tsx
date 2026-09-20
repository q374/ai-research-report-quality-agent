"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, ClipboardCheck } from "lucide-react";

import { getAPIClient } from "@/core/api";
import { getEvidenceValidation } from "@/core/api/evidence-validation";
import type { EvidenceValidationRecord } from "@/core/api/evidence-validation";

interface EvidenceValidationBannerProps {
  threadId?: string | null;
  enabled?: boolean;
}

export interface EvidenceValidationSummary {
  title: string;
  countText: string;
  blockerDetails: string[];
}

export function summarizeEvidenceValidation(
  record: EvidenceValidationRecord,
): EvidenceValidationSummary {
  const blockers = record.finding_counts?.blocker ?? 0;
  const warnings = record.finding_counts?.warning ?? 0;
  const title =
    record.status === "blocked"
      ? "质量校验：暂不建议发布"
      : record.status === "confirmed"
        ? "质量校验：已通过"
        : "质量校验：需要人工复核";
  const countText = [
    blockers > 0 ? `${blockers} 个阻断问题` : "没有阻断问题",
    warnings > 0 ? `${warnings} 个提醒` : null,
  ]
    .filter(Boolean)
    .join("，");
  const blockerDetails = (record.findings ?? [])
    .filter((finding) => finding.severity === "blocker")
    .slice(0, 3)
    .map((finding) => {
      const action = finding.required_action
        ? ` 建议：${finding.required_action}`
        : "";
      return `${finding.rule_id}：${finding.message}${action}`;
    });
  return { title, countText, blockerDetails };
}

export function EvidenceValidationBanner({
  threadId,
  enabled = true,
}: EvidenceValidationBannerProps) {
  const query = useQuery<EvidenceValidationRecord | null>({
    queryKey: ["thread", threadId, "latest-evidence-validation"],
    queryFn: async () => {
      if (!threadId) return null;
      const runs = await getAPIClient().runs.list(threadId);
      const latest = [...runs]
        .filter((run) => run.status === "success")
        .sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
      if (!latest) return null;
      return getEvidenceValidation(threadId, latest.run_id);
    },
    enabled: enabled && Boolean(threadId),
    retry: false,
    refetchInterval: (result) => (result.state.data ? false : 5000),
    refetchOnWindowFocus: false,
  });

  const record = query.data;
  if (!record) return null;

  const summary = summarizeEvidenceValidation(record);
  const isBlocked = record.status === "blocked";
  const isConfirmed = record.status === "confirmed";

  return (
    <div
      className="mx-auto mb-2 flex w-full max-w-(--container-width-md) items-start gap-2 rounded-lg border px-3 py-2 text-xs"
      role="status"
      data-testid="evidence-validation-banner"
    >
      {isBlocked ? (
        <AlertTriangle className="mt-0.5 size-4 text-destructive" />
      ) : isConfirmed ? (
        <CheckCircle2 className="mt-0.5 size-4 text-emerald-600" />
      ) : (
        <ClipboardCheck className="mt-0.5 size-4 text-amber-600" />
      )}
      <div className="min-w-0">
        <div className="font-medium">{summary.title}</div>
        <div className="text-muted-foreground">
          {summary.countText}。模型回答成功不代表报告可以直接发布。
        </div>
        {summary.blockerDetails.length > 0 && (
          <ul className="text-muted-foreground mt-1 list-disc space-y-0.5 pl-4">
            {summary.blockerDetails.map((detail) => (
              <li key={detail}>{detail}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
