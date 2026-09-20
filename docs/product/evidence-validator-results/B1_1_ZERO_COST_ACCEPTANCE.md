# B1.1 零费用集成验收

日期：2026-09-20

## 1. 结论

**有条件 Go：可以进入“单个真实付费样本”的独立审批，但不能进入批量测试、B2 硬门禁或生产发布。**

B1.1 已证明结构化证据提交、持久事件采集、确定性校验和可点击引用能在零真实模型调用下闭环。Docker Desktop 本轮再次出现 `dockerInference` 启动错误，因此 Docker 容器态没有通过；本轮改用同一代码、`config.yaml` 与 SQLite 的本机 Gateway 进程完成等价重启验证。该结果不能表述为 Docker 部署验收通过。

## 2. 真实性边界

- 验收对象是程序化构造的 `b1-1-zero-cost-*` run/event，不是真实模型样本，也不代表未知样本准确率。
- 没有发送 DeerFlow 消息，没有访问模型接口，新增模型调用 0，新增 API 费用 0 元。
- 程序化 run 中的 `llm_call_count=1` 是用于核对“重启前后字段不变”的假数据；结构化结束工具的独立假模型测试也证明只调用假模型 1 次。
- 没有执行 T002，没有重跑 T001，没有设置 Claim、Evidence、摘录或 Token 的产品硬上限。
- 没有推送、发布或改动 Dify 数据。

## 3. 本机运行验收

| 检查项 | 结果 | 证据 |
|---|---|---|
| 事件存储 | 通过 | Git 忽略的 `config.yaml` 将 `run_events.backend` 由 `memory` 改为 `db`；未出现在 Git 状态 |
| Gateway 健康 | 通过 | 两次本机 Gateway 进程启动后 `/health` 均为 `healthy` |
| OpenAPI | 通过 | 保留 2 条 evidence-validation 路径：查询与重放 |
| 持久化重启 | 通过 | 第一次进程写入 6 条 event、1 条 run、1 条 validation；第二次进程仍读到相同数量 |
| 关联一致性 | 通过 | `evidence.report.submitted`、最终 `ai_message` 与 validation 的 `message_id` 均为 `b1-1-zero-cost-message`；重新计算的 `report_hash` 一致 |
| 主 run 不变 | 通过 | 重启前后均为 `status=success`、`total_tokens=42`、`llm_call_count=1` |
| 所有者隔离 | 通过 | 其他合成 owner 查询 event 与 validation 均为空 |
| 非持久事件告警 | 通过 | 两次新 Gateway 日志中 `non-persistent` 命中 0 |
| 模型请求 | 通过 | 两次新 Gateway 日志中 `chat/completions` 命中 0 |
| 测试数据清理 | 通过 | 清理前 6 event / 1 run / 1 validation；清理后全部为 0 |
| Dify | 未运行 | Docker 引擎未成功启动，因此没有容器运行；无法取得成功的 `docker ps` 服务端快照 |
| Docker 部署 | 受阻 | Docker Desktop 再次报 `dockerInference` 通信端点错误；未重置、未删除数据、未继续盲目重试 |

补充边界：Gateway 仍提示 LangGraph checkpointer/store 使用内存，这是线程列表持久化问题；它与本次已经切换为 DB 的 run events 不是同一层能力，不能混为一谈。

## 4. 自动化验证

- 后端 B1.1 专项、所有者与退出边界：92 项通过，2 条 warning。
- 产品测试：31 项通过。
- B0 回放：8 个样本；`false_releases=0`、`false_blocks=0`、`mismatches=0`。
- 引用浏览器测试：`thread-history.spec.ts` 共 11 项通过；验证“来源1”可见、`href` 正确、`target=_blank`、`rel` 含 `noopener noreferrer`，没有真正访问外部网页。
- 前端 TypeScript 检查通过；Next.js 构建通过，保留一条既有 Turbopack NFT warning。
- Ruff、`compileall`、`git diff --check` 通过。
- 修改前后端全量基线：4,747 passed、78 failed、21 skipped、18 warnings。
- 本轮后端全量：4,799 passed、79 failed、24 skipped、18 warnings。并非全绿。
- 相对基线唯一新失败为 `tests/test_mcp_file_migration.py::TestWorkspaceSnapshots::test_changed_workspace_files_detects_created_and_modified_files`；隔离重跑可复现，原因是 Windows 下同字节长度文件被立即改写时，大小不变且文件时间精度不足，快照漏判 modified。该测试不经过 B1.1 模块；B1.1 专项无失败。本轮不扩大范围修改无关 MCP 逻辑。

## 5. 产品决策

### 已实现

1. 研究 profile 可在同一次生成中提交结构化 Claim/Evidence 候选，不使用第二个评分模型。
2. 确定性结束中间件生成最终 AI 消息，假模型调用数保持 1。
3. 持久化事件区分系统观测、Agent 候选和人工决定；Agent 不能把候选证据直接写成 confirmed。
4. 证据校验记录与 `message_id`、`report_hash` 绑定，报告变化时可识别为新版本。
5. 用户可见报告中的“来源 N”渲染为安全的新窗口链接。

### 尚未验证

- 新结构在一个真实 DeepSeek 研究样本中的 Token、调用次数、延迟、费用和结构体积。
- 未知样本的误报率、漏报率和人工复核效率。
- Docker 部署态的本轮 B1.1 重启验收。
- B2 发布硬门禁、人工 confirmed 写接口和生产稳定性。

### 下一关

必须由用户另行确认**一个真实付费样本**的任务、模型、范围和费用边界。该授权不能从本次零费用验收自动推导；在确认前不发送研究任务。
