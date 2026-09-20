# T001 B1.1 真实付费样本记录

更新时间：2026-09-20

## 结论

本次授权的一个真实付费样本已执行完成，但 **B1.1 结构化证据收尾未通过**，不能把它写成质量门禁通过，也不能继续执行 T002 或批量样本。

## 样本范围

- 任务：`T001-b1-1-real`
- 模型：DeepSeek Flash（`deepseek-flash`）
- 仅 1 次运行；没有自动重试、没有第二次付费调用、没有执行 T002。
- 研究约束：仅允许 OpenAI 官方域名，最多 2 次搜索、4 个页面、报告不超过 800 个总字符。

## 实际运行证据

- `run_id`：`ce2c87d0-dba9-47f4-bdeb-cb843136cf3c`
- 状态：运行层 `success`
- 延迟：203.096 秒
- 输入 41,677、输出 1,782、合计 43,459 tokens
- 模型调用 5 次；工具调用 9 次（搜索 5、页面查看 3、提交报告 1）
- 按本项目已记录的 DeepSeek Flash 高峰未缓存价格 2/8 元每百万 tokens 估算约 **0.09761 元**；最终账单未核对，以 DeepSeek 账单为准。

## 发现的问题

1. 模型确实生成了报告和候选 Claim/Evidence，但报告正文实际为 1,047 个总字符，超过本次 800 字符约束。
2. 候选证据包含 `community.openai.com`，不符合“仅 OpenAI 官方来源”的白名单；这是可直接记录的质量问题。
3. `submit_evidence_report` 收尾失败。模型提交的字段使用了 `type/source`、`source/snippet/supports`，而系统契约要求 `claim_id/claim_type/dimension/evidence_ids` 与 `evidence_id/source_url/excerpt/proposed_relation` 等字段。事件中明确记录了 Pydantic 校验错误。
4. 因提交失败，没有产生 `evidence.report.submitted` 和最终 `ai_message` 事件；查询验证记录返回 404，`semantic_evaluation` 无法执行。运行层显示 success 不能解释为证据校验通过。
5. 页面抓取工具出现 Jina 匿名访问 401，模型随后使用搜索摘要继续完成了提交；这属于工具可用性风险，不能当作页面内容已成功核验。

## 产品判断

当前判定：**No-Go**。

下一步只做零费用修复和测试：把结构化字段契约以模型更容易遵循的方式提供给模型；用固定样本和假模型验证成功、失败、超长和域名越界路径。修复并通过零费用验收后，另行申请一次真实付费复测；在此之前不重跑本样本、不执行 T002、不批量调用。

## 2026-09-20 零费用修复结果

- 根因已确认：工具对外暴露的是 `list[dict]`，实际传给模型的 Schema 只说明“这是对象列表”，没有列出 Claim/Evidence 的必填字段；模型只能自行猜字段，因而生成了错误结构。
- 已把工具参数改为明确的 `ClaimCandidate` 和 `EvidenceCandidate` 类型。转换后的实际工具 Schema 现在包含全部必填字段和枚举值，没有放宽后端校验，也没有接受错误字段来伪造成功。
- 新增回归测试先复现“Schema 没有内层字段”的失败，再验证修复。结构化提交相关测试 31 项通过，B1.1 专项 93 项通过，产品测试 31 项通过，B0 的 8 个固定样本仍为错误放行 0、错误阻断 0、不一致 0；Ruff 通过。
- 后端全量为 4,804 passed、78 failed、21 skipped，不是全绿；失败仍集中在既有 Windows/POSIX、文件权限和路径差异，B1.1 相关测试无失败。
- 本次修复没有联网、没有调用模型、没有产生新增 API 费用。它只证明工具契约已正确暴露，尚未证明 DeepSeek 在真实任务中一定会按契约提交。
- 当前状态：零费用修复 **通过**；真实效果仍保持 **No-Go**，下一次真实复测必须重新获得单次费用授权。

## 证据位置

- 原始运行摘要：`.superpowers/sdd/2026-09-19-persistent-evidence-contract/paid-sample-result.json`
- 提交参数与校验错误：`.superpowers/sdd/2026-09-19-persistent-evidence-contract/paid-sample-submit-args.json` 及运行事件 API
- 临时 Gateway 日志：`.superpowers/sdd/2026-09-19-persistent-evidence-contract/paid-sample-local-gateway.log`
