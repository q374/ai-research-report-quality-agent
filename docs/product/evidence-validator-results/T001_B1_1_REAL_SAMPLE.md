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

下一步只做零费用修复和测试：把结构化字段契约以模型更容易遵循的方式注入工具说明，并增加“工具参数校验失败时的可观察失败记录”；用固定样本和假模型验证成功、失败、超长和域名越界路径。修复并通过零费用验收后，另行申请一次真实付费复测；在此之前不重跑本样本、不执行 T002、不批量调用。

## 证据位置

- 原始运行摘要：`.superpowers/sdd/2026-09-19-persistent-evidence-contract/paid-sample-result.json`
- 提交参数与校验错误：`.superpowers/sdd/2026-09-19-persistent-evidence-contract/paid-sample-submit-args.json` 及运行事件 API
- 临时 Gateway 日志：`.superpowers/sdd/2026-09-19-persistent-evidence-contract/paid-sample-local-gateway.log`

