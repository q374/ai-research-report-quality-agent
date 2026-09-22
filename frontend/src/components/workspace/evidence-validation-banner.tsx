"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, ClipboardCheck } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { getAPIClient } from "@/core/api";
import {
  buildEvidenceReviewIdempotencyKey,
  getEvidenceValidation,
  submitEvidenceReview,
} from "@/core/api/evidence-validation";
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
      : record.status === "rejected"
        ? "质量校验：已拒绝发布"
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
  const queryClient = useQueryClient();
  const [reason, setReason] = useState("");
  const [reviewError, setReviewError] = useState<string | null>(null);
  const queryKey = ["thread", threadId, "latest-evidence-validation"] as const;
  const query = useQuery<EvidenceValidationRecord | null>({
    queryKey,
    queryFn: async () => {
      if (!threadId) return null;
      const runs = await getAPIClient().runs.list(threadId);
      const latest = [...runs]
        .filter((run) => run.status === "success")
        .sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
      if (!latest) return null;
      const validation = await getEvidenceValidation(threadId, latest.run_id);
      return validation ? { ...validation, run_id: latest.run_id } : null;
    },
    enabled: enabled && Boolean(threadId),
    retry: false,
    refetchInterval: (result) => (result.state.data ? false : 5000),
    refetchOnWindowFocus: false,
  });

  const record = query.data;
  const reviewMutation = useMutation({
    mutationFn: async (decision: "approved" | "returned" | "rejected") => {
      if (
        !threadId ||
        !record?.run_id ||
        !record.validation_id ||
        !record.report_hash
      ) {
        throw new Error("缺少报告版本信息，请刷新页面后重试。");
      }
      const normalizedReason = reason.trim();
      if (decision !== "approved" && !normalizedReason) {
        throw new Error("退回或拒绝时必须填写理由。");
      }
      const idempotencyKey = buildEvidenceReviewIdempotencyKey(
        record.validation_id,
        decision,
      );
      return submitEvidenceReview(threadId, record.run_id, {
        decision,
        expected_report_hash: record.report_hash,
        idempotency_key: idempotencyKey,
        ...(normalizedReason ? { reason: normalizedReason } : {}),
      });
    },
    onMutate: () => setReviewError(null),
    onSuccess: (updated) => {
      queryClient.setQueryData(queryKey, {
        ...updated,
        run_id: record?.run_id,
      });
      setReason("");
    },
    onError: (error) => {
      setReviewError(
        error instanceof Error ? error.message : "人工复核提交失败，请重试。",
      );
    },
  });
  if (!record) return null;

  const summary = summarizeEvidenceValidation(record);
  const latestReview = record.review_decisions?.at(-1);
  const isBlocked = record.status === "blocked";
  const isConfirmed = record.status === "confirmed";
  const canReview =
    (record.status === "review_required" || record.status === "blocked") &&
    Boolean(record.report_hash) &&
    (record.review_decisions?.length ?? 0) === 0;

  return (
    <div
      className="max-w-(--container-width-md) mx-auto mb-2 mt-12 flex w-full shrink-0 items-start gap-2 rounded-lg border px-3 py-2 text-xs"
      role="status"
      data-testid="evidence-validation-banner"
    >
      {isBlocked ? (
        <AlertTriangle className="text-destructive mt-0.5 size-4" />
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
        {latestReview?.reason && (
          <div className="text-muted-foreground mt-1">
            复核意见：{latestReview.reason}
          </div>
        )}
        {summary.blockerDetails.length > 0 && (
          <ul className="text-muted-foreground mt-1 list-disc space-y-0.5 pl-4">
            {summary.blockerDetails.map((detail) => (
              <li key={detail}>{detail}</li>
            ))}
          </ul>
        )}
        {canReview && (
          <div
            className="mt-2 space-y-2"
            data-testid="evidence-review-controls"
          >
            <Textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              placeholder="退回修改或拒绝发布时，请填写理由"
              className="min-h-16 text-xs"
              aria-label="复核理由"
            />
            <div className="flex flex-wrap gap-2">
              {record.status === "review_required" && (
                <Button
                  size="sm"
                  onClick={() => reviewMutation.mutate("approved")}
                  disabled={reviewMutation.isPending}
                >
                  确认通过
                </Button>
              )}
              <Button
                size="sm"
                variant="outline"
                onClick={() => reviewMutation.mutate("returned")}
                disabled={reviewMutation.isPending}
              >
                退回修改
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={() => reviewMutation.mutate("rejected")}
                disabled={reviewMutation.isPending}
              >
                拒绝发布
              </Button>
            </div>
            {reviewError && (
              <div className="text-destructive" role="alert">
                {reviewError}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
