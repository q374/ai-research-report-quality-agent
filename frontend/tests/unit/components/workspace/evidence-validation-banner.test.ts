import { describe, expect, it } from "@rstest/core";

import { summarizeEvidenceValidation } from "@/components/workspace/evidence-validation-banner";
import type { EvidenceValidationRecord } from "@/core/api/evidence-validation";

describe("summarizeEvidenceValidation", () => {
  it("shows blocker reasons and required actions for a blocked report", () => {
    const record: EvidenceValidationRecord = {
      status: "blocked",
      finding_counts: { blocker: 2, warning: 1 },
      findings: [
        {
          rule_id: "EV-05",
          severity: "blocker",
          message: "可见引用链接与结构化证据绑定不一致。",
          required_action: "修正引用与证据绑定。",
        },
        {
          rule_id: "EV-06",
          severity: "blocker",
          message: "正文超过长度上限。",
          required_action: "缩减正文后重新校验。",
        },
        {
          rule_id: "EV-07",
          severity: "warning",
          message: "存在重复页面访问。",
        },
      ],
    };

    expect(summarizeEvidenceValidation(record)).toEqual({
      title: "质量校验：暂不建议发布",
      countText: "2 个阻断问题，1 个提醒",
      blockerDetails: [
        "EV-05：可见引用链接与结构化证据绑定不一致。 建议：修正引用与证据绑定。",
        "EV-06：正文超过长度上限。 建议：缩减正文后重新校验。",
      ],
    });
  });

  it("distinguishes human review from confirmed status", () => {
    expect(
      summarizeEvidenceValidation({
        status: "review_required",
        finding_counts: { blocker: 0, warning: 1 },
      }),
    ).toMatchObject({
      title: "质量校验：需要人工复核",
      countText: "没有阻断问题，1 个提醒",
    });
    expect(
      summarizeEvidenceValidation({
        status: "confirmed",
        finding_counts: { blocker: 0, warning: 0 },
      }),
    ).toMatchObject({
      title: "质量校验：已通过",
      countText: "没有阻断问题",
    });
  });
});
