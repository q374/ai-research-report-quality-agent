# B1 证据校验影子运行设计

版本：v1.0  
日期：2026-09-19  
状态：已完成对话设计确认，待书面规格复核

## 1. 目标

把 B0 的离线证据校验契约接到 DeerFlow 的真实运行记录上，但不改变用户获得原回答的流程。第一版只对指定测试账号和 `evidence-research-v1` 质量配置启用；校验在回答完成后运行并持久化，主页面暂不展示，不阻断、不自动重跑、不增加模型调用。

成功后，产品负责人能够针对一条真实 DeerFlow run 回答：系统实际生成了什么、访问了哪些页面、消耗了多少 Token、哪些确定性规则命中、哪些语义信息目前无法自动判断。

## 2. 用户与使用场景

- 主要使用者：产品负责人和质量评测人员。
- 第一阶段对象：单一指定测试账号，不开放给普通用户。
- 使用场景：研究任务完成后，后台形成一条影子校验记录；产品负责人通过受权限保护的只读接口检查结果。
- 普通用户行为：回答正常出现，不感知影子校验是否成功。

## 3. 已确认约束

1. 只对服务端允许的测试账号和指定质量配置启用。
2. 校验结果不进入真实回答页面。
3. 不阻断回答、不自动重跑任务、不调用第二个模型。
4. 系统字符、页面、搜索、工具和 Token 必须来自运行记录，不采用模型自报值。
5. 校验器异常记录为 `validator_error`，但不把原 run 改成失败。
6. 所有记录绑定 user、thread、run、message 和 report_hash。
7. 数据进入 DeerFlow 现有数据库，通过 Alembic 迁移管理。
8. 不执行新付费任务；首次真实链路验证优先回放已有成功 run。
9. 不修改 frontend，不推送、不发布。

## 4. 方案比较

### 方案 A：回答展示前同步硬门禁

优点是用户立即看到阻断结果；缺点是规则和真实数据映射尚未稳定，一旦误报会直接影响主流程。当前不采用。

### 方案 B：继续用独立 JSON 文件批处理

实现快、隔离强，但刷新恢复、权限和真实运行绑定仍是假设，与 B0 的能力重复。当前不采用。

### 方案 C：运行完成后的数据库影子校验（采用）

回答完成后由应用层读取真实 run 和 event，生成并保存校验记录。它能验证真实数据链路，又不影响主回答，是当前风险和学习价值最平衡的方案。

## 5. 产品状态语义

影子运行需要同时区分两层状态：

- **原 run 状态**：DeerFlow 自己的 `success`、`error` 等，不受影子校验修改。
- **校验状态**：`blocked`、`review_required`、`validator_error`。

B1 不生成 `confirmed`。`confirmed` 只能在后续接入真实人工决定后产生。即使校验结果是 `blocked`，原回答仍正常展示；这里只表示“若将来启用发布门禁，这份报告不应发布”。

## 6. 系统架构

### 6.1 校验核心单一来源

B0 的确定性规则提升为 `deerflow.evaluation.evidence_validator` 下的无网络、无数据库纯函数模块，作为 B0 回放和 B1 影子服务共同调用的唯一规则实现。根目录现有脚本保留为薄包装器，用于兼容原离线命令和测试；不得复制第二套规则，避免离线结果与真实链路漂移。

### 6.2 应用层影子服务

新增独立的 ShadowValidationService，职责只有四项：

1. 判断 run 是否满足账号、质量配置和完成状态条件。
2. 从 RunStore 与 RunEventStore 收集系统事实。
3. 调用确定性校验核心形成 ValidationRecord。
4. 将记录幂等写入数据库。

服务放在 Gateway 应用层，由应用调用 harness 提供的运行与持久化接口；不允许 harness 反向导入 `app.*`，保持现有依赖边界。

### 6.3 触发方式

`start_run` 创建的后台任务完成后，应用层注册的完成回调触发影子服务。回调只处理：

- run 状态为 `success`；
- `metadata.quality_profile_id == "evidence-research-v1"`；
- run 的 user_id 在服务端允许列表中。

影子处理失败只能写日志或 `validator_error` 记录，不能修改 run 状态、SSE 结果或最终回答。

为验证已有 run 和修复漏处理，增加一个受所有者权限保护的幂等重放入口。它只读取已有数据库记录并运行确定性校验，不调用模型或工具。

### 6.4 数据来源

| 数据 | 权威来源 | B1 处理 |
|---|---|---|
| 最终回答 | RunStore 的 last_ai_message，并与最后 AI message 事件核对 | 计算 report_hash 和实际字符数 |
| 搜索、页面、工具 | RunEventStore 的 trace/tool 事件 | 统计实际事件和 URL |
| Token、模型调用数 | RunStore 完成字段 | 原样记录，不信模型自报 |
| 用户、线程、运行 | RunStore | 权限和审计绑定 |
| ResearchBrief | run metadata 中的受控质量配置字段 | 缺失时标记输入不完整 |
| Claim / Evidence 语义绑定 | 仅接受明确结构化输入 | 缺失时不使用模型或正则伪造 |

### 6.5 语义能力边界

现有 DeerFlow 普通回答没有稳定的 Claim / Evidence 结构。B1 不从自然语言中猜测它们，也不额外调用模型抽取。

因此：

- 字符数、Token、搜索、页面和工具等系统事实可以真实校验。
- 若 run 没有结构化 Claim / Evidence，EV-02 至 EV-05 等语义规则标为输入不完整，并进入不可发布或人工复核状态。
- 记录必须明确 `semantic_evaluation = not_evaluable`，不能把“无法判断”写成“已通过”。
- 后续 B1.1 再单独评审是否让研究配置原生输出结构化 Claim / Evidence；本阶段不扩张。

## 7. 持久化设计

新增 `evidence_validations` 表，由新的 Alembic revision 创建，不修改既有表语义。

核心字段：

- validation_id
- schema_version
- user_id
- thread_id
- run_id
- message_id
- quality_profile_id
- report_hash
- source_payload_json
- validation_result_json
- auto_status
- semantic_evaluation
- created_at / updated_at

约束：

- `(run_id, report_hash)` 唯一，重复回调或重放不得产生重复记录。
- user_id、thread_id、run_id 建索引，支持权限过滤和问题追踪。
- 报告变化后产生新 report_hash，旧记录保留，不能覆盖历史版本。
- B1 暂不创建 ReviewDecision 写接口；真实人工决定属于下一阶段，避免把静态演示误写成已接通审批。

## 8. 配置与权限

新增默认关闭的影子配置：

- `enabled: false`
- `quality_profile_ids: ["evidence-research-v1"]`
- `allowed_user_ids: []`

实际测试账号 ID 只放本机未提交配置或环境变量，不写入仓库。

只读查询和重放接口沿用现有 owner check：

- 非所有者返回 404，避免泄露 run 是否存在。
- run 必须属于路径中的 thread。
- 重放仍需满足服务端账号与质量配置允许条件。
- 返回内容不得包含密钥、内部异常堆栈或完整未截断的敏感工具参数。

## 9. 接口

### 查询影子结果

`GET /api/threads/{thread_id}/runs/{run_id}/evidence-validation`

- 找到：返回当前 run 的校验记录。
- 尚未生成：返回 404，不伪造“通过”。
- 仅所有者可访问。

### 幂等重放

`POST /api/threads/{thread_id}/runs/{run_id}/evidence-validation/replay`

- 只处理已有 run 和 event。
- 不启动 Agent、不调用模型、不访问外网。
- 相同 report_hash 返回同一记录。
- 不符合账号或质量配置时返回明确的 409/403，不静默启用。

## 10. 异常处理

| 异常 | 处理 |
|---|---|
| run 未成功 | 跳过，不生成误导性记录 |
| 不符合账号或质量配置 | 跳过；手动重放返回拒绝 |
| 最终回答缺失 | 保存 `validator_error` 或输入不完整记录 |
| event 缺失或被截断 | 在记录中标记数据缺口，不把 0 当作真实行为 |
| 校验器抛异常 | 保存安全的 EV-10 信息，不暴露内部堆栈 |
| 数据库写入失败 | 记录脱敏日志，原 run 仍保持成功 |
| 重复回调 | 依靠唯一约束和幂等 upsert 返回原记录 |

影子模式对主回答采用 fail-open，对校验状态本身采用 fail-closed：主回答不受影响，但校验失败绝不能显示为通过。

## 11. 验收标准

1. 普通聊天和非允许账号不会生成校验记录。
2. 指定账号 + 指定质量配置 + 成功 run 会生成一条记录。
3. 记录的 user/thread/run/report_hash 与真实运行一致。
4. 字符、Token、搜索、页面和工具统计来自系统记录。
5. 缺少结构化 Claim / Evidence 时明确显示 `not_evaluable`。
6. 同一 run 重复触发或重放不产生重复记录。
7. Gateway 重启后记录仍可查询。
8. 非所有者无法读取或重放记录。
9. 校验异常不改变原 run 的 success 状态。
10. 自动校验不能产生 confirmed。
11. 测试和日志证明新增模型调用为 0。
12. 使用已有成功 run 完成一次本机端到端重放，避免新增 API 费用。

## 12. 测试策略

- 纯函数测试：真实事件到系统指标和校验输入的映射。
- 服务测试：启用条件、幂等、异常隔离和状态边界。
- 数据库测试：Alembic 迁移、唯一约束、SQLite 重启后读取。
- API 测试：owner check、thread/run 绑定、404/409 和脱敏输出。
- 回归测试：B0 的 8 份固定样本和全部产品测试继续通过。
- 本机验收：重放一条已有成功 run，核对数据库记录和健康状态。

## 13. 实施范围

预计修改：

- B0 规则核心迁移为 backend 内单一权威模块，根目录脚本保留兼容包装。
- Gateway 配置、依赖注入、服务与路由。
- harness persistence 中的新 ORM model、repository 和 Alembic revision。
- run 完成后的应用层影子触发器。
- backend 测试和相关 README/CLAUDE 文档。
- 产品验收文档和项目 MEMORY。

明确不修改：

- frontend 用户界面。
- Agent 主提示词和模型选择。
- 普通聊天默认行为。
- 外部发布、云部署或生产配置。

## 14. 交付与学习顺序

1. 先用测试和模拟事件跑通采集、校验、持久化和权限。
2. 再用已有真实成功 run 做一次零新增费用重放。
3. 向用户展示一条影子记录，解释系统事实、模型输出和人工判断的区别。
4. 用户在引导下亲自查看一次结果并做产品判断。
5. 最后整理 B1 指标、风险和面试表达；不把本机验证包装成生产上线。
