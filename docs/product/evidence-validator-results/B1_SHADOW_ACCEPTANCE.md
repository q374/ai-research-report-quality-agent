# B1 证据校验影子模式验收

日期：2026-09-19

范围：本机单账号、已有成功 run、零新增模型调用的手动重放
结论：**B1 本地影子链路通过；不进入全量硬门禁。**

## 1. 这次实现了什么

- 真实 run 完成后可在允许账号和质量配置范围内异步生成证据校验记录，不阻塞、不改写主回答或 run 状态。
- 可对已有成功 run 执行手动重放；只读取数据库和当前 event store，不启动 Agent、不访问外网、不调用模型。
- 记录持久化到 `evidence_validations`，迁移版本为 `0003_evidence_validations`；同一 `(run_id, report_hash)` 幂等。
- 提供所有者保护的 GET 查询和 POST 重放接口；功能默认关闭，本机验收时仅在 Git 忽略的 `config.yaml` 中允许一个测试账号和 `evidence-research-v1`。

## 2. 真实验收对象

| 字段 | 值 |
|---|---|
| 用户 | `4997...39f7`（脱敏） |
| thread_id | `6604da82-dd28-47a2-9223-23f36fc31182` |
| run_id | `f66e3bce-6be5-4548-a508-08323076a6ca` |
| 原 run 状态 | `success` |
| 模型 | `deepseek-flash` |
| 来源 | `manual_replay` |

这是先前已授权并完成的 T001 v3 运行，不是本次新生成的样本。

## 3. 零新增模型调用证据

重放前后数据库中的 run 计数一致：

| 指标 | 重放前 | 两次重放后 |
|---|---:|---:|
| 输入 Tokens | 48,491 | 48,491 |
| 输出 Tokens | 965 | 965 |
| 总 Tokens | 49,456 | 49,456 |
| 模型调用数 | 5 | 5 |
| run 状态 | success | success |

验收窗口内 Gateway 日志中的 `chat/completions` 新增行数为 0。因此本次重放新增模型调用 0 次，新增模型费用 0 元；这里只证明 DeerFlow 本机记录和 Gateway 日志未增加，最终外部账单仍以供应商为准。

## 4. 校验结果

| 字段 | 结果 |
|---|---|
| validation_id | `765df865-e4ad-5997-bb8b-42f80b6dbc69` |
| report_hash | `e0b0a3f12ce5544c9baff76f1383ec013ca74caf4d341a9702cd56c8d3d229e7` |
| auto_status | `review_required` |
| semantic_evaluation | `not_evaluable` |
| 系统计算字符数 | 1,406 |
| 搜索数 | 0（见数据缺口） |
| 页面查看数 / 唯一页 | 0 / 0（见数据缺口） |
| 已采集工具 | 空（见数据缺口） |

数据缺口：

- `missing_final_answer_event`
- `missing_structured_claims_or_evidence`

T001 v3 原始体验中确有搜索和页面查看，但当时 `run_events.backend=memory`，Gateway 为加载 B1 代码发生重启后，旧事件不能恢复。因此这里的 0 只表示“当前 event store 没有可采集事件”，不能解释为原任务没有搜索或页面行为。校验器保留缺口并把语义状态标为 `not_evaluable`，没有伪造语义通过。

系统字符数 1,406 来自持久化 `last_ai_message`，与 B0 固定夹具中的 877 字符不是同一输入快照，不能互相替代。

## 5. 幂等、重启和权限

- 同一 POST 重放两次均返回 HTTP 200，`validation_id` 和 `report_hash` 完全一致；数据库只有 1 条该 run 的记录。
- 重启 Gateway 后，GET 返回 HTTP 200，仍是同一 `validation_id` 和 `report_hash`。
- 当前登录账号请求不存在的 run 返回 HTTP 404。
- 自动化测试已覆盖其他所有者返回 404、thread/run 不匹配、非允许账号 403、非允许 profile 409。
- 本机只有一个真实账号，因此没有创建第二个真实账号做手工越权测试；不能把自动化权限测试说成第二账号真实验收。

## 6. 验证范围

- B1 专项测试：35 passed。
- 持久化、边界与关闭顺序：49 passed。
- 产品契约与静态原型：31 passed。
- B0 固定回放：8 个样本，错误放行 0、错误阻断 0、不一致 0。
- Ruff、Python 编译、`git diff --check`：通过。
- 后端全量：4,746 passed、79 failed、21 skipped。改动前基线为 4,722 passed、66 failed、21 skipped；B1 专项无失败。新增全量失败集中在 Windows 路径/时间戳与测试相互影响：13 个目录迁移用例隔离重跑全部通过；另一个工作区快照用例因 Windows 文件时间戳未变化而失败，未修改其代码。全量测试不能标记为全绿。

## 7. 仍未验证

- 普通回答缺少稳定的 Claim/Evidence 结构，语义规则尚不能评价真实回答内容是否被证据支持。
- 旧 run 的 memory event 无法跨重启恢复；要评估真实搜索/页面行为，需要把 run events 改成可持久化后再生成新样本。
- 尚未验证未知样本误报率、真实复核耗时、真实用户价值、生产并发稳定性。
- 尚未实现 B2 的人工审批写接口和硬发布门禁；`review_required` 不等于事实已确认。
- 没有运行 T002，没有新增付费样本，没有推送或发布。

## 8. AI 产品经理学习要点

1. “功能能运行”不等于“数据足以判断质量”：本次链路可用，但语义输入和历史事件不足。
2. 影子模式先观测、不拦主流程，适合在误报率未知时降低上线风险。
3. 系统事实、模型输出、人工决定必须分层；模型不能自己证明 Token、工具次数或事实正确。
4. `report_hash` 把人工决定绑定到具体报告版本，避免报告改变后继续沿用旧批准。
5. 下一步不是继续堆提示词，而是先补持久化事件与结构化 Claim/Evidence，再测误报率和复核效率。
