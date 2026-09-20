# 产品项目记忆

更新时间：2026-09-20

- 当前目标：B1.1 零费用实现与验收已完成；停在一个真实付费样本的独立授权门前，不运行 T002、不批量测试。
- 目录：D:\AI产品经理简历\项目经历\product-intelligence-agent。
- 基线：v2.0.0 / 7e7f0410797693cf882594555ba414e0361d4c6f；开发分支 codex/product-intelligence-mvp。origin 与 upstream 均指向官方仓库，不推送。
- 迁移验证：1388 个文件，除路径检查自动更新的 .git/index 缓存外 SHA256 一致；索引 ls-files --stage 一致；git fsck --full 通过。原版源码未改动。
- 本目录新增 AGENTS.md、MEMORY.md 为项目规则与状态，不是产品功能。
- 运行入口：Install.md、Makefile、scripts/docker.sh、docker/docker-compose-dev.yaml。backend/frontend 子目录规则按需读取。
- 当前运行：Docker Desktop 于 2026-09-20 再次出现 dockerInference 启动错误，本轮未重置或删除数据；B1.1 使用本机 Gateway 完成等价验收后已停止。Dify 未运行。
- 当前评测：T001 v1 至 v3 已执行；最新 v3 得分 36、判定“需改进”。阶段 A、B0、B1 与 B1.1 零费用闭环已完成；B1.1 程序化 run 为 evaluated，但不代表真实模型效果。等待用户另行授权一个真实付费样本。
- 产品规格与评测证据见 `docs/product/PRODUCT_OPPORTUNITY.md` 和 `docs/product/DEERFLOW_EVALUATION_SCORECARD.xlsx`；始终保留合成数据、真实 API、人工复核和生产发布之间的真实性边界。

## 模型输入准备
- 2026-09-18 官方文档复核：当前 Flash 模型名为 deepseek-flash，高峰未缓存输入/输出价格为 2/8 元每百万 tokens。旧模型名不再用于新配置。
- 学习目录 tools/deepseek-connection-check.ps1 已通过语法检查；本地密码框只在内存使用密钥，点击确认后发一次请求，输出上限 128、不重试；只保存状态和用量，不保存密钥。测试结果在学习目录 outputs/deepseek-check-*.json，实际结果待核查。
- 输入程序使用仅当前进程 RemoteSigned，未修改系统策略。窗口有 10 分钟自动关闭时限，旧进程号不得当作持续运行保证。
- Docker 磁盘位置尚未确认，未构建镜像、安装依赖或启动原版。迁移实际释放约 91.55 MiB，C 盘只保留约 79 KB 原任务入口与旧 Git 历史。
## 2026-09-18 DeepSeek 最小连接已验证

- 用户已在产品根目录 .env 填写 DEEPSEEK_API_KEY；仅程序读取用于鉴权，不输出或复制至源码。文件由 Git 忽略。
- 单次官方接口测试 HTTP 200，期望回复匹配；输入 10、输出 2，共 12 tokens；按高峰未缓存价格估算 0.000036 元，实际以账单为准。无重试；本任务已确认调用累计 1 次，其他项目费用未核实。
- 脱敏证据：D:\AI产品经理简历\学习资料\deerflow-learning\outputs\deepseek-env-first-check.json。禁止重复该次测试，避免重复扣费。
- 通过官方 scripts/configure.py 生成 config.yaml 与 frontend/.env，哈希核对原 .env 未变；模型配置引用 $DEEPSEEK_API_KEY，deepseek-flash 非思考模式、输出上限 2048、重试 0。YAML 解析与 Git 忽略检查通过。
- 仅证明 API 连通及配置语法正确；DeerFlow 依赖尚未安装、原版未启动、工具调用与完整任务链未验证。下一步先核实 Docker 磁盘与资源落点，再准备原版服务，不把本次连接测试当成研究任务验收。

## 2026-09-18 原版安装受阻：Docker 启动错误

- 已确认 Docker 数据盘位于 D:\dify\dify-main\docker\image\DockerDesktopWSL，未移动或修改其虚拟磁盘。DeerFlow 尚未构建、安装或启动。
- Docker Desktop 启动日志与用户截图均报 initializing Inference manager / dockerInference 无法访问。run 目录中的 dockerInference 是零长度 ReparsePoint，fsutil 查询返回错误 1920；不是 DeepSeek 密钥或 DeerFlow 代码错误。
- 已停止重复等待引擎的检查进程，未恢复出厂设置、删除通信文件、上传诊断或重启系统。
- Docker 官方问题跟踪仓库有同类用户报告：https://github.com/docker/desktop-feedback/issues/460 ，报告提出退出 Docker 后重命名通信目录的临时绕行，但不代表官方已验证修复，也可能随后遇到其他端点错误。
- 下一步建议先正常退出本次失败的 Docker，再将只含三个已核对通信端点的 run 目录重命名保留，尝试重新生成并启动；此项修复尚待用户确认。不得碰镜像、容器卷、其他目录或直接重置；备选为用户保存工作后重启电脑。

## 2026-09-18 Docker 有限修复未成功，停止重复尝试

- 经用户确认且核对路径、进程退出及目录内容后，分别将两个只含通信端点的目录改名保留：C:\Users\zengc\AppData\Local\Docker\run.backup-20260918-194917；C:\Users\zengc\AppData\Local\docker-secrets-engine.backup-20260918-195347。未删除数据、未修改 Docker 虚拟磁盘。
- 第一次重启由 dockerInference 报错推进到 engine.sock；第二次又回到 dockerInference。同类故障复现，绕行无效；不继续逐个清理、改名或盲目重启 Docker。
- 第二次正常退出失败，已核对安装路径后仅结束 Docker Desktop/后台进程，再进行已授权目录改名。未停止其他应用或重启整个 WSL。
- 用户最新截图确认仍启动失败。引擎等待检查已停止；没有安装 DeerFlow 依赖、构建镜像、启动项目或追加模型调用。Docker 错误窗口可能仍在，不能当作引擎已运行。
- 推荐下一步：用户先保存所有工作并重启 Windows（尚未执行或授权自动重启）。重启后只做一次引擎连接检查，核对自动恢复的 Dify 容器和资源；若仍失败，再基于新日志评估版本修复或非 Docker 路径，不恢复出厂、不注销 WSL、不删除虚拟磁盘。

## 重启 Windows 后复核
- 用户确认已重启，重新启动 Docker 后截图仍报 dockerInference；引擎限时检查未通过，停止重复等待。未继续改名目录、重置、删除镜像或安装新版本。
- 已核对 v2.0.0 README_zh.md：官方支持 Windows Git Bash 本地开发，也支持 DeerFlowClient 内嵌入口；无需更换主项目。Python 已有版本满足 >=3.12，但前后端依赖尚未安装，nginx 未在路径发现，兼容性未实测。
- 推荐改用官方本地开发路径，项目依赖和缓存定向 D 盘；保留 allow_host_bash=false，不把本地执行误称容器隔离。替代是继续专项修复 Docker，涉及版本/系统变更需单独确认。等待用户选择，尚未切换方案。


## 2026-09-18 Docker 恢复验证

- Windows 重启后首次命令检查时 Docker 尚未启动；用户随后手动打开 Docker Desktop。当前连续复核已返回客户端/服务端 29.6.2，docker info 正常，因此引擎现已恢复，不再改通信目录或重装。
- 恢复原因只能确认与系统重启后重新启动 Docker 的时序有关；无法证明此前的目录改名是必要修复。保留两个 backup 目录，暂不删除，待稳定运行后再清理。
- Docker 自动恢复了 14 个 Dify 容器，DeerFlow 的 2026/3000/8001 端口仍空闲；但物理内存快照仅剩约 0.23 GiB，当前不能安全构建 DeerFlow。
- 下一步需再次确认停止自动恢复的 Dify 容器，释放内存后复核；不改变其 restart policy、不删除容器或卷。之后按 Docker 原版开发模式构建 DeerFlow，并逐层验证容器、后端、页面。

## 2026-09-19 DeerFlow 原版已启动，待创建本机管理员

- 用户授权按推荐方案停止整套 Dify：已停止 14 个 Dify 容器，未删除容器或卷，未修改 restart policy。Docker Desktop 重启时它们仍可能因 `restart=always` 自动启动；当前 DeerFlow 运行期间不要同时恢复 Dify。
- 资源处理：16 GiB 主机在构建前最低仅约 0.66 GiB 可用；通过 WSL 内 `sync` 与 `drop_caches` 只释放可回收缓存，未删除镜像或数据。采用串行构建，避免前后端同时抢内存。
- 为避免 Windows 主机 pnpm 缓存占用 C 盘，使用学习目录 `tools/compose.local.yaml` 将前端 pnpm store 改为 Docker 命名卷；原版源码未因此修改。
- 已成功构建 `deer-flow-dev-frontend:latest`（约 405 MiB）和 `deer-flow-dev-gateway:latest`（约 482 MiB）。随后启动 frontend、gateway、nginx；未启动 Kubernetes provisioner，沿用本地 sandbox 与 `allow_host_bash=false`。
- 运行验证：三个容器持续运行；`http://localhost:2026`、`/health`、`/openapi.json` 均返回 HTTP 200，健康响应为 deer-flow-gateway healthy；最近日志未见 error/exception/traceback/fatal。`/api/models` 在未登录时返回 401，属于鉴权边界，不作为模型失败证据。
- 浏览器实际截图已显示 `/setup` 的 Create admin account 表单；gateway 同时记录 first boot、无管理员。尚未创建本机管理员账号，等待用户在页面内自行设置，不在聊天或记忆中保存邮箱/密码。
- 本阶段没有新增 DeepSeek 生成调用；累计仍仅有此前 1 次、12 tokens 的最小连通测试。创建管理员后还需验证登录、模型列表与第一条受控任务，实际任务调用须再次确认预算和范围。
- 运行告警：Gateway 使用 SQLite 持久化基础数据，但 config 未配置 checkpointer/store，日志说明部分 thread/store 状态在服务重启后可能丢失；原版体验阶段先保留现状，产品化前再设计持久化。

## 2026-09-19 本机管理员创建完成

- 用户已在 DeerFlow 页面内自行创建本机管理员；未在聊天、日志或记忆中保存邮箱和密码。
- 浏览器实际工作区已显示中文欢迎页、对话输入框、闪速模式和 `DeepSeek Flash` 模型选择，证明登录会话与模型配置已被前端读取。
- 尚未发送首条 DeerFlow 任务；除既有最小连通测试外没有新增 DeepSeek 调用。下一步需获得单次低成本任务授权，再验证完整回答链路、用量与日志。

## 2026-09-19 原版首条真实任务完成

- 用户在 DeerFlow 工作区自行发送：`请用不超过50个汉字说明 DeerFlow 能做什么。不要联网，不调用任何工具`；未由 Codex 重复发送。
- 线程 `9cf569a7-2d6d-4a47-8ca8-6f0e4628e4d4`，主运行 `291c0779-519c-4b90-b788-147cd5334c61`，模型 `deepseek-flash`，thinking=false，subagent=false，运行状态 success。
- 主回答可见且无工具调用产物；主回答用量输入 8,360、输出 37、合计 8,397。线程持久化总量输入 8,451、输出 43、合计 8,494，额外 97 tokens 来自辅助流程的一部分。
- Gateway 日志记录本次交互期间 4 次 DeepSeek `chat/completions` HTTP 200（包含主任务及标题/建议等自动辅助请求）；因此一次用户发送不等于一次底层 API 请求。应用 Token 面板可能不覆盖平台账单的全部辅助消耗。
- 按高峰未缓存输入/输出 2/8 元每百万 tokens 对线程已记录 8,494 tokens 估算约 0.017246 元；这是应用记录部分估算，最终以 DeepSeek 账单为准。
- 回答后 frontend、gateway、nginx 持续运行，`/health` 返回 healthy；Dify 运行容器数 0，可用物理内存约 1.66 GiB。至此 DeerFlow v2.0.0 原版从启动、登录、模型读取到真实回答的基础闭环已验证；联网检索、工具执行、sandbox 文件能力尚未验证。

## 2026-09-19 教学方向纠正

- 用户明确不学习代码，目标是学习与 AI 产品经理岗位强相关的知识。
- 后续由 Codex 负责源码、配置、日志和技术查证；面向用户只讲产品定位、用户场景、Agent 工作机制、质量评测、成本与延迟、风险边界、MVP 决策、数据指标及面试表达。
- 教学继续采用真实 DeerFlow 运行证据，但不要求用户阅读函数或理解编程语法；每一步都要落到产品判断与可交付产物。

## 2026-09-19 产品发现初稿

- 已创建 `docs/product/PRODUCT_OPPORTUNITY.md`，定位为面向 AI 产品经理和中小产品团队的证据优先产品情报智能体。
- 文档包含目标用户假设、JTBD、待验证痛点、MVP 输入/工作流/输出、非目标、暂定验收指标、真实基线证据和下一步验证。
- 用户需求尚未经过真实访谈；当前只可称为产品假设。已验证部分仅限原版基础对话闭环，不包含联网研究、引用正确性、工具调用或真实用户价值。
- 下一步先设计 5 个合成竞品研究任务和评分表，不立即追加付费 API 调用。

## 2026-09-19 合成评测题集与评分表

- 已创建 `docs/product/DEERFLOW_EVALUATION_SCORECARD.xlsx`，包含“概览、评测记录、评分标准”三个工作表。
- 题集共 5 条合成任务，覆盖官方事实核验、多竞品比较、价格与可用性、来源冲突处理和决策备忘录；明确不是生产数据或真实用户任务。
- 评分维度及权重：来源正确性 30%、引用覆盖 20%、分析完整性 20%、指令遵循 15%、产品可用性 15%。发布闸门同时要求得分不低于 80、人工复核通过、高风险无依据结论为 0。
- 表内可记录输入/输出 Tokens、延迟、费用、Badcase、证据路径和人工结论；费用公式使用可编辑的 DeepSeek Flash 高峰未缓存价格。
- 已完成视觉预览、重新导入和公式扫描：3 个工作表、5 条任务、权重合计 100%，无公式错误。尚未运行任何题集任务，本阶段没有新增 API 调用或费用。

## 2026-09-19 T001 联网检索评测

- 用户明确授权单次 T001 付费评测；未据此扩展到 T002 或重跑。使用 DeepSeek Flash、闪速模式，线程 `bed321a8-d6eb-4a57-9a70-6bbb5f59f3f3`。
- 运行完成 2 次搜索、3 次页面查看，实际读取 2 个唯一 OpenAI 官方页面；未使用第三方来源、子智能体或文件生成。UI 观测延迟约 17 秒，服务随后仍为 healthy。
- 主回复输入约 41.8K、输出 1,142 tokens；线程顶部显示输入 42.1K、输出 1,150、总量 43.2K。评分表按主回复近似值估算 0.092736 元；应用存在取整与辅助调用，最终以 DeepSeek 账单为准。
- 人工复核评分：来源正确性 3、引用覆盖 4、分析完整性 3、指令遵循 4、产品可用性 3；加权 67。高风险无依据结论 0，人工结论“需修改”，发布闸门“需改进”。
- 主要 Badcase：引用均为官方来源，但把发布时的 o3 与 o4-mini 机制写成当前事实；遗漏官方页面明确列出的幻觉、错误推断、权威来源识别和置信度校准限制；“未找到量化指标”与同页 26.6% 基准信息冲突。
- 产品结论：官方域名白名单只能控制来源范围，不能自动保证时效和结论正确。下一版研究规则必须增加当前文档优先级、历史信息时间标注、关键限制提取和引用支持关系复核。
- 证据已登记到 `docs/product/DEERFLOW_EVALUATION_SCORECARD.xlsx`；产品发现文档同步更新。未获新费用授权前不重跑 T001、不执行 T002。

## 2026-09-19 研究质量门禁 v1.1

- 已创建 `docs/product/RESEARCH_QUALITY_GATES.md`，将 T001 Badcase 转为 7 项产品质量门禁：当前性、证据一致性、引用覆盖、限制完整性、冲突与未知、范围与成本、可审计性。
- 门禁明确当前官方文档优先于历史发布页；历史信息必须标注时间；链接存在但不支持结论仍视为无有效引用；否定性结论不得由“未找到”直接推导。
- 已定义 T001 v2 的通过条件、受控评测指令和人工复核清单。输出上限改为 800 个总字符，避免只统计汉字造成范围歧义。
- `docs/product/DEERFLOW_EVALUATION_SCORECARD.xlsx` 的评分标准页已同步 v1.1 规则，并新增 QG-01 至 QG-07 门禁表；T001 原始得分与 Badcase 保持不变，不用新规则篡改历史结果。
- 本阶段只修改规则与文档，没有调用模型、没有产生 API 费用。已用现有 T001 结果完成免费走查：QG-01、QG-02、QG-04、QG-05 未通过，QG-03 部分通过，QG-06、QG-07 通过；说明规则能识别已知 Badcase。未获新授权前不重跑 T001、不执行 T002。

## 2026-09-19 T001 v2 回归评测

- 用户明确授权单次 T001 v2 付费回归；未据此执行 T002 或额外重跑。线程 `a58c5f86-f156-476d-af45-24c12a78c8c5`，使用 DeepSeek Flash、闪速模式。
- 完成 2 次搜索、3 次页面查看、3 个唯一 OpenAI 官方页面；未见第三方来源、子智能体或文件生成。UI 观测延迟约 10 秒，正文 575 个总字符。
- 主回复输入约 32.4K、输出 900 tokens，评分表估算约 0.072 元；线程顶部显示输入 32.7K、输出 909、总量 33.6K。实际费用以 DeepSeek 账单为准。
- 人工复核评分：来源正确性 4、引用覆盖 4、分析完整性 3、指令遵循 5、产品可用性 4；加权 79。高风险无依据结论 0，人工结论“需修改”，发布闸门“需改进”。
- v2 已正确分开当前事实与历史信息，并满足搜索、页面、工具和总字符限制；较 v1 得分增加 12，主回复成本约下降 22%，正文长度约下降 55%。
- 剩余 Badcase：仍遗漏幻觉、错误推断、权威来源识别和置信度校准等模型质量限制；“Pro $200 暂停注册”无所读官方页支持，却被引入待复核项。
- 决策：不把 79 分上调为通过，不执行 T002。先修正规则，未获新费用授权前不运行 T001 v3。

## 2026-09-19 研究质量门禁 v1.2

- 已将 T001 v2 的剩余 Badcase 固化为 v1.2 规则：未知或待人工复核项不得引入无依据事实前提；事件、价格和可用性前提也必须有直接官方来源。
- 已明确区分操作、权限、套餐和额度限制与模型质量失败模式；已读官方页面披露质量问题时，至少提取 2 项，前者不能替代后者。
- 已同步更新 `docs/product/RESEARCH_QUALITY_GATES.md`、`docs/product/PRODUCT_OPPORTUNITY.md` 和评分表规则，并定义 T001 v3 受控指令。
- 本阶段只做规则和文档修正，没有调用模型、没有产生 API 费用。T001 v2 的 79 分和“需改进”历史结论保持不变。
- 下一步：运行 T001 v3 前必须获得新的单次费用授权；T001 通过前不执行 T002。

## 2026-09-19 T001 v3 回归评测

- 用户明确授权单次 T001 v3 付费回归；没有自动重试，也没有执行 T002。线程 `6604da82-dd28-47a2-9223-23f36fc31182`，DeepSeek Flash、闪速模式。
- 完成 2 次搜索、4 次页面查看；按去除 URL 片段计算 3 个唯一 URL，实质主要依赖 2 篇 OpenAI 官方文章。未见第三方来源、子智能体或文件生成。UI 观测延迟约 5 秒。
- 主轮输入约 48.2K、输出 957、总量约 49.1K tokens，估算约 0.104056 元；线程顶部输入 48.5K、输出 965、总量 49.5K。实际费用以 DeepSeek 账单为准。
- 人工复核评分：来源正确性 2、引用覆盖 2、分析完整性 1、指令遵循 2、产品可用性 2；加权 36。高风险无依据结论 0，人工结论“需修改”，发布闸门“需改进”。
- 正向变化：当前与历史信息已分区；待复核项改为中性问题，没有继续引入“套餐暂停”等无依据事件前提。
- 关键失败：模型已查看官方发布页 limitations 段，却错误写成“页面未披露”幻觉、错误推断、权威来源识别和置信度校准问题；页面可见正文 877 个总字符，却自报约 560 并声称符合 800 上限。
- 决策：停止继续堆叠提示词或扩大付费样本。先免费设计确定性证据校验，包括否定性结论反查、必填维度覆盖、程序字符计数、URL 规范化和人工发布闸门；能拦截 T001 v1 至 v3 已知 Badcase 后再考虑新付费回归。

## 2026-09-19 独立证据校验器 v1.0 设计

- 已创建 `docs/product/EVIDENCE_VALIDATOR_SPEC.md`，定义研究 Agent 与人工发布之间的独立质量闸门。核心对象为 ResearchBrief、Claim、EvidenceItem、ValidationFinding、ResearchReport；证据状态使用 pending、confirmed、conflict、stale。
- 首版定义 EV-01 至 EV-10：当前性、结论—证据绑定、否定性结论反查、必填维度覆盖、引用直接性、字符与范围、URL 规范化、待复核项前提、冲突过期、审计完整性。
- 发布状态为 blocked、review_required、confirmed、rejected；存在任一未解决阻断项即 fail-closed，自动校验不能替代人工批准。
- 已创建 `docs/product/EVIDENCE_VALIDATOR_OFFLINE_WALKTHROUGH.md`，用 T001 v1 至 v3 既有结果进行人工离线走查。8 项已知阻断问题均能映射到规则，三条样本均应 blocked；这是规则覆盖走查，不是程序召回率或生产效果。
- 设计阶段没有调用模型、没有新增 API 费用、没有修改 DeerFlow 原版生成链。程序实现尚未开始。
- 下一步：先由用户评审规格；确认后再进入阶段 A 离线确定性原型，只复用既有样本，不联网、不调用模型。


## 2026-09-19 独立证据校验器阶段 A 离线原型

- 已实现 `scripts/evidence_validator.py`，使用 Python 标准库执行 EV-01 至 EV-10 的离线确定性检查；不联网、不调用模型、不增加第三方依赖，也未修改 DeerFlow 前后端生成链。
- 已保存 T001 v1 至 v3 的结构化固定夹具和结果。程序计算正文字符数为 1217、575、877；v3 的 4 次页面查看经锚点和别名归一后为 2 个唯一页面。
- 7 项单元测试全部通过；三份已知 Badcase 均为 `blocked`，8 项人工登记的已知阻断问题全部命中，无错误放行。无阻断对照样本仍需人工批准才能从 `review_required` 进入 `confirmed`。
- 真实性边界：结果只覆盖三份已知合成样本；尚未验证未知样本、误报率、真实用户效率或生产稳定性。Claim、EvidenceItem 和运行日志目前由固定夹具提供，尚未从 DeerFlow 自动采集。
- 本阶段新增模型调用 0 次，新增 API 费用 0 元。下一步先做产品评审，确认输入契约和误报风险；未经新范围确认，不接入 DeerFlow、不运行 T002 或新的付费样本。
- 验证入口：`docs/product/evidence-validator-results/SUMMARY.md`；实现与测试入口：`scripts/evidence_validator.py`、`tests/product/test_evidence_validator.py`。


## 2026-09-19 阶段 B 接入评审

- 已核对 DeerFlow 的 ThreadState、Run API、运行事件、引用组件、前端 onFinish 和 Feedback API。现有系统可提供 run/message/tool/Token/artifact/身份基础，但没有证据校验状态和版本化人工审批。
- 产品决策：证据研究仅作为显式质量配置，不作用于普通聊天；系统字符、工具、页面、Token 等数据必须来自运行记录，不能相信模型自报。
- 现有点赞/点踩仅代表满意度，不复用为发布审批。建议新增 ValidationRecord 与追加式 ReviewDecision；人工批准必须绑定 report_hash、复核人和时间，报告变化后旧批准失效。
- 复核界面采用回答下方状态卡和问题/证据抽屉；有 blocker 时不能确认，校验器异常时使用 validator_error 并 fail-closed。失败报告仍可查看，但明确标为不可发布。
- Go/No-Go：有条件进入 B0 契约与固定样本回放；暂不进入全量前后端硬门禁、不运行 T002、不新增付费样本。B0 完成 B-01 至 B-10 且新增至少 5 个无阻断或边界对照样本后，再评估影子运行。
- 评审文档：`docs/product/STAGE_B_INTEGRATION_REVIEW.md`。本阶段未修改 DeerFlow 前后端、未调用模型、未产生 API 费用。

## 2026-09-19 独立证据校验器 B0 离线实现

- 已完成 ValidationRecord / ReviewDecision 可执行契约：绑定 thread、run、message、owner 和 report_hash；覆盖权限、幂等、旧哈希失效及 validator_error fail-closed。
- 已完成 8 份固定样本回放：T001 v1 至 v3 三份负样本全部 blocked，5 份正向/边界样本全部 review_required；固定样本内错误放行 0、错误阻断 0。
- 已完成四状态静态复核界面，桌面浏览器逐态检查通过；blocked 与 validator_error 的确认按钮禁用。窄屏浏览器实测和截图落盘因当前 CUA 能力限制未完成；响应式规则仅完成源码检查，不能替代真实窄屏验收。
- 完整产品测试 31 项通过；本阶段没有联网、模型调用或新增 API 费用，也没有修改 DeerFlow backend/frontend。
- 真实性边界：所有输入仍是本地固定夹具；人工决定只在内存契约中演示，未接数据库或登录 API。B-10 的刷新持久化、真实运行事件映射、未知样本准确率、生产稳定性和真实用户价值均未验证。
- 下一步先做 B1 影子运行设计评审，明确服务端持久化和 run/message/tool 事件映射；未获新授权前不修改真实链路、不运行新付费样本、不推送或发布。
## 2026-09-19 B1 影子校验设计与实施计划

- 已完成设计规格 `docs/superpowers/specs/2026-09-19-evidence-validation-shadow-mode-design.md` 和实施计划 `docs/superpowers/plans/2026-09-19-evidence-validation-shadow-mode.md`；当前仍是设计与计划，不代表功能已实现。
- 方案只面向允许的测试账号与 `evidence-research-v1`：原回答照常显示，后台读取真实 run/event 事实做确定性校验，结果写入新表；异常不得改写原 run。
- 自动回调要求 run metadata 含质量配置；已有 run 可由允许账号显式提交质量配置与 ResearchBrief 做手动零费用重放，且不修改原 run metadata、不调用模型。
- 缺少结构化 Claim/Evidence 必须标为 `not_evaluable`；自动流程不能产生人工确认。查询和重放都要求所有者权限，跨用户统一 404。
- 计划已补齐并发幂等、异常脱敏、数据库迁移、重启持久化、backend 全量测试与旧 run 零新增模型调用验收。下一步等待用户确认按当前任务串行执行；确认前不修改 backend。
## 2026-09-19 B1 证据校验影子链路验收

- 分支 `codex/product-intelligence-mvp`；B1 实现提交包括 `e1e57216`、`616eefa3`、`1639d0ed`、`20a04a75`、`6b1804d3`，最终文档提交尚待本轮完成。未推送、未发布。
- 已接入确定性校验核心、默认关闭的账号/profile 灰度、Alembic `0003_evidence_validations`、幂等 SQL 仓储、run/event 采集、后台影子调度及受保护 GET/POST API。影子失败不改变主 run。
- 本机 Git 忽略的 `config.yaml` 只允许 1 个真实测试账号和 `evidence-research-v1`；账号 ID、密钥和完整工具参数未提交。
- 使用既有 T001 v3 run `f66e3bce-6be5-4548-a508-08323076a6ca` 做两次手动重放，均 HTTP 200 且 validation_id 相同。输入 48,491、输出 965、总量 49,456、模型调用数 5 前后不变；验收窗口新增 chat/completions 日志 0，故本次新增模型调用和费用均为 0。
- Gateway 重启后 GET 仍返回同一 validation_id/report_hash；不存在 run 返回 404。第二真实账号手工越权未测，自动化跨所有者 404 已通过。
- 真实记录状态为 review_required / not_evaluable。因为旧 run events 使用 memory backend 且已重启，搜索、页面和工具无法恢复，记录明确包含 missing_final_answer_event；0 次观测不能解释为原任务没有工具行为。
- 验证：B1 专项 35 passed；持久化和边界 49 passed；产品测试 31 passed；B0 8 样本零不一致；Ruff、compileall、diff-check 通过。后端全量为 4,746 passed、79 failed、21 skipped，不是全绿；失败为既有 Windows 差异及隔离可复现的 Windows 时间戳/顺序问题，B1 专项无失败。
- 当前 Docker 的 frontend、gateway、nginx 健康，Dify 运行容器 0。详细验收见 `docs/product/evidence-validator-results/B1_SHADOW_ACCEPTANCE.md`。
- 下一步教学入口：先用大白话讲“为什么影子模式不等于上线门禁、为什么 not_evaluable 反而是诚实结果、AI 产品经理怎样用数据缺口决定下一版”，再由用户在引导下完成一次 Go/No-Go 判断。未经新授权不运行 T002、不新增付费模型调用。
## 2026-09-19 B1.1 持久化证据与结构化结论设计

- 用户确认采用“同一次研究提交结构化证据”的方案：用户可见报告保留正常 Markdown，重要结论旁使用 DeerFlow 已支持的可点击“来源 N”标签；后台保存 Claim/Evidence 候选关系，不使用第二个评分模型。
- 系统事实、Agent 候选与人工决定分层：系统记录访问、工具、Token 和延迟；Agent 只能提出支持关系；B1.1 不实现人工 confirmed 写接口。
- 运行事件复用现有 DbRunEventStore/run_events 表；证据模式要求重启后可读取。若仍使用 memory，主回答继续，但质检必须记录 non_persistent_event_store，不能冒充完成持久化验收。
- 结构化结束契约名为 submit_evidence_report；必须直接结束并用测试证明其后没有为了质检新增模型调用。普通聊天、未允许账号和未启用 profile 的 run 保持原样。
- 用户明确决定暂不设置 Claim、Evidence、摘录或 Token 的产品硬上限；先在免费离线与零费用集成测试通过后，另行授权一个真实付费样本，记录 Token、调用、延迟、费用和结构体积，再决定阈值。不得据此自动运行 T002 或批量样本。
- 正式规格：docs/superpowers/specs/2026-09-19-persistent-evidence-contract-design.md。当前只是设计，不代表已实现；本阶段没有模型调用或 API 费用。下一步等待用户书面规格复核，确认后才能进入实施计划。
## 2026-09-19 B1.1 实施计划

- 用户已确认 `docs/superpowers/specs/2026-09-19-persistent-evidence-contract-design.md`；这只确认规格，不等于授权跳过实施计划复核。
- 已创建 `docs/superpowers/plans/2026-09-19-persistent-evidence-contract.md`，拆为 7 个任务：提交契约、直接结束工具、profile 灰度、事件持久化就绪、真实事件采集、确定性校验闭环、引用与本机零费用验收。
- 计划执行阶段不调用真实模型、不运行 T002、不设置 Token 产品硬上限；先用假模型和程序化 run 证明直接结束、跨重启持久化、引用跳转和 B0 兼容。一个真实付费样本仍需计划完成后单独授权。
- 当前未修改产品代码、未调用模型、未产生 API 费用。下一步等待用户确认计划并选择执行方式；推荐当前任务原地串行执行，便于沿用本机 SQLite、Docker 和忽略配置，且不增加多智能体协调成本。

## 2026-09-19 B1.1 任务 2 设计闸门

- 用户已确认按推荐方案原地串行执行。任务 1 已提交为 `a8767ed6`：结构化 Claim/Evidence 契约、HTTP(S) 来源脱敏、可点击引用 URL 提取及“暂不设数量/长度产品上限”测试均通过；真实模型调用 0、费用 0。
- 修改前后端全量基线为 4,747 passed、78 failed、21 skipped；不是全绿，失败主要是既有 Windows/POSIX 与本机环境差异，后续只把专项通过算作本次成果。
- 任务 2 的真实 LangChain 1.2.15 假模型集成测试发现：`return_direct=True` 工具若通过 `Command` 追加 `[ToolMessage, AIMessage]`，框架仍调用模型第 2 次。根因是 tools-to-model 路由读取最后新增的无 tool_calls AIMessage，因而回到 model；追加 `goto=END` 也不能改变该行为。
- 已用零费用探针验证替代：工具只返回 ToolMessage，让 return_direct 正常退出；专用 after_agent 中间件再确定性补写最终 AIMessage。结果为模型调用 1 次，末尾消息 `[tool, ai]`，正文正确。
- 该替代会把“AIMessage 由工具直接追加”改为“由确定性结束中间件追加”，用户结果和成本目标不变，但属于实现架构修订。用户已于 2026-09-20 明确确认按此修正版继续；不得用第二次模型调用绕过。
## 2026-09-20 B1.1 零费用实现与验收

- 任务 1—6 已完成并本地提交：结构化提交契约、确定性直接结束、账号/profile 门禁、事件持久化就绪、真实事件观测映射和持久化校验闭环。任务 7 的引用安全与 Gateway 兼容修复提交为 `7e9b9cd8`；未推送、未发布。
- `submit_evidence_report` 使用 ToolMessage + 确定性 after-agent 中间件形成最终 AIMessage；真实 LangChain 假模型测试保持 1 次调用，没有为质检追加第二次模型调用。
- Git 忽略的 `config.yaml` 已将 `run_events.backend` 改为 `db`。程序化 `b1-1-zero-cost-*` 数据在两次本机 Gateway 进程间保持：6 event、1 run、1 validation；message_id/report_hash 一致，run 的 success、42 tokens、llm_call_count=1 不变；新日志 chat/completions 为 0。
- 合成测试数据已按 owner 范围清理，清理后 event/run/validation 均为 0。该 run 不是模型样本，42 tokens 和调用数 1 只是持久化断言数据；本阶段新增真实模型调用 0、费用 0 元。
- 引用 E2E 11 项通过，验证“来源1”链接文本、URL、新窗口与 noopener/noreferrer；没有访问外部页面。后端专项 92 项、产品 31 项、B0 8 样本回放、Ruff、compileall、类型检查和构建通过。
- 后端全量不是全绿：基线 4,747 passed / 78 failed / 21 skipped；本轮 4,799 passed / 79 failed / 24 skipped。唯一新增失败是无关 MCP 文件快照测试在 Windows 同大小立即改写时漏判 modified；已隔离归因，B1.1 专项无失败。
- Docker Desktop 本轮再次出现 dockerInference 通信端点错误；未重置、未删除数据、未继续盲试。因而只证明同代码/配置/SQLite 的本机 Gateway 重启，不声称 Docker 部署验收通过。Dify 未运行。
- 详细报告：`docs/product/evidence-validator-results/B1_1_ZERO_COST_ACCEPTANCE.md`。Go 到“一个真实付费样本的独立审批”；No-Go 到 T002、批量样本、B2 硬门禁和生产发布。Token/Claim/Evidence 硬上限继续暂不设置。

## 2026-09-20 B1.1 一个真实付费样本

- 用户明确授权且只执行 1 个真实样本：`T001-b1-1-real`、DeepSeek Flash；没有自动重试、没有执行 T002 或批量任务。运行 `ce2c87d0-dba9-47f4-bdeb-cb843136cf3c`，状态 success，延迟 203.096 秒，输入 41,677、输出 1,782、总计 43,459 tokens，模型调用 5 次，估算费用约 0.09761 元，最终账单未核对。
- 工具实际调用搜索 5 次、页面查看 3 次、结构化提交 1 次。页面查看出现 Jina 匿名访问 401，模型改用搜索摘要继续，不能把页面内容写成已成功核验。
- 真实样本发现收尾缺陷：模型提交的 Claim/Evidence 字段与 Pydantic 契约不一致，事件记录明确校验错误；因此没有 `evidence.report.submitted` 或最终 `ai_message`，验证记录查询为 404，不能把运行 success 当成质量通过。报告正文程序计数 1,047 个总字符，超过本样本 800 限制；候选证据还包含 `community.openai.com`，违反官方域名白名单。
- 配置已恢复到样本前版本，临时本机 Gateway 已停止，Docker gateway 重启后 `/health`=200；Dify 运行容器仍为 0。没有保留临时测试账号授权。
- 详细记录：`docs/product/evidence-validator-results/T001_B1_1_REAL_SAMPLE.md`。当前 No-Go：先零费用修复结构化契约和失败可观察性，再另行申请一次付费复测；不重跑本样本、不执行 T002、不批量调用。

## 2026-09-20 B1.1 真实样本后的零费用修复

- 根因已通过实际 OpenAI 兼容工具 Schema 确认：`submit_evidence_report` 的 `claims/evidence` 原类型为 `list[dict]`，模型只能看到任意对象，无法看到 Pydantic 契约要求的内层字段；真实样本因此猜错字段并在工具执行时失败。
- 已改为 `list[ClaimCandidate]` 与 `list[EvidenceCandidate]`，最终工具 Schema 现在明确列出全部必填字段和枚举值；没有放宽校验、没有把错误字段映射成成功。新增回归测试先失败后通过，假模型单次调用与 finalizer 行为保持不变。
- 验证：结构化提交相关 31 passed；B1.1 专项 93 passed；产品 31 passed；B0 8 样本错误放行 0、错误阻断 0、不一致 0；Ruff 通过。后端全量为 4,804 passed / 78 failed / 21 skipped，不是全绿，B1.1 相关测试无失败。
- 本轮没有联网、模型调用或新增费用。零费用修复已通过，但真实 DeepSeek 是否稳定遵循新 Schema 尚未验证；继续停在一次真实付费复测的独立授权门前，不执行 T002 或批量调用。

## 2026-09-20 B1.1 单次真实付费复测

- 用户重新明确授权后只执行 `T001-b1-1-retest` 1 个真实运行；未自动重跑、未执行 T002 或批量任务。运行 `04e68807-5706-473f-8b66-9cc637c0a4ca` 为 success，输入 76,867、输出 1,735、合计 78,602 tokens，底层模型调用 8 次，估算 0.167614 元，最终账单未核对。研究运行约 110 秒；诊断总时长 292.895 秒包含约 180 秒等待缺失自动校验。
- 工具调用 13 次：搜索 6、页面查看 6、结构化提交 1。Schema 修复在真实 DeepSeek 上生效：产生结构化提交和最终 AI message，message_id 一致，包含 4 Claim、2 Evidence；最终报告引用只使用 `openai.com` 与 `help.openai.com`。
- 自动 validation 未产生。零费用重放同一持久事件后为 `semantic_evaluation=evaluated`、`blocked`：EV-12 两项、EV-05、EV-04、EV-06 为 blocker，EV-07 为 warning。系统计数 1,079 字符、搜索 6、页面查看 6，超过 800/2/4 限制；Jina 页面抓取仍有 401；人工还发现历史可用性信息被放入当前事实。
- 自动调度缺陷根因已确认：普通用户运行未把当前用户 ID 写入 `RunRecord`，dispatcher 因 `record.user_id=None` 跳过；数据库后续依靠上下文补写用户，所以手动重放可成功。已显式传递当前用户 ID，同时保持可信内部 owner 优先级；回归测试先失败后通过，权限/调度相关 31 passed、Ruff 通过。
- 后端全量仍为 4,804 passed / 78 failed / 21 skipped，与修复前一致；本轮修复后没有再次调用模型。临时 Gateway 已停止，临时账号配置已恢复，Dify 保持停止。下一步只做零费用自动调度和质量规则验收，不追加付费样本。

## 2026-09-20 教学方式再次确认

- 用户再次明确：学习必须绑定本项目真实运行数据、测试结果和产品决策，不能切换成脱离项目的通用课程列表。
- 每次恢复或新对话先读取本目录 `AGENTS.md` 与 `MEMORY.md`，再核对产品目录当前 Git、运行与测试状态；解释采用“数据 → 大白话 → 产品判断 → AI 产品经理能力总结”。
- 当前教学下一步固定为：先做零费用自动调度验收，再用验收结果解释“为什么此前运行成功但没有自动校验”，然后让用户根据真实 blocker 做一次 Go/No-Go 判断；未经单独授权不新增真实模型调用。

## 2026-09-20 阶段一自动校验验收与加固

- 按 insert → verify → cleanup 执行既有程序化零费用验收脚本；验证后事件、run、validation 均恢复为 0，未调用真实模型，新增 API 费用 0 元。
- 验收结果：6 个事件、1 个 run、1 个 validation 可跨进程读取；`run_status=success`、`semantic_evaluation=evaluated`、`message_id_match=true`、`report_hash_match=true`、`owner_isolation=true`、`model_api_calls=0`。
- 相关回归专项 103 项通过；随后加入普通登录用户 owner→dispatcher 回归测试，服务层/调度/持久化/权限隔离组合测试 65 项通过。新增提交 `eaef6245 test: cover authenticated owner shadow validation`。
- 本阶段确认的产品含义：任务成功后可以自动生成质量校验，且不会改写主任务结果；下一步不是继续扩大付费样本，而是进入阶段二，优先解决真实复测中的报告质量和用户可见性问题。

## 2026-09-20 阶段二第一项：质量状态用户可见

- 前端新增质量校验结果读取与提示：聊天页会读取最近一次成功 run 的 evidence validation；当状态为 `blocked`、`review_required` 或 `confirmed` 时显示对应中文提示和阻断/提醒数量。无校验记录时不打扰普通聊天。
- 后端已有受保护的 run 级校验接口，前端现在真正接入该接口，避免“后台发现问题但用户看不到”的产品断层。
- 前端验证：现有 node_modules 直接执行 TypeScript 检查通过；新增文件及聊天页 ESLint 通过。提交 `bb9d158d feat: surface evidence validation status in chat`。
- 当前未调用真实模型、未增加费用；Docker Gateway 仍健康。下一项优先补充真实 blocker 的用户可读详情与前端回归测试，再做阶段二的完整基本流程验收。

## 2026-09-20 阶段二第二项：阻断原因与前后端契约修复

- 质量提示现在不仅显示 `blocked/review_required/confirmed`，还会显示最多 3 条 blocker 的规则编号、原因和整改建议，避免用户只看到“不能发布”却不知道怎么改。
- 测试中发现真实后端接口把状态放在 `validation_result` 内，前端初版错误地按顶层字段读取；新增接口契约测试先失败，随后修正为规范化后端 envelope，再供 UI 使用。提交 `d081190d fix: normalize evidence validation API response`。
- 新增详情摘要测试先失败后通过；前端全量单元测试 37 个文件、341 项全部通过，TypeScript 与相关 ESLint 通过。详情提交 `dfa981ca feat: explain evidence validation blockers`。
- Docker 前端镜像重建因 npm registry 多次 `ECONNRESET` 失败，不归因于代码；现有开发容器保持运行、源码目录已挂载、首页 HTTP 200。浏览器真实视觉验收仍需现有本机登录会话或独立 mock E2E，不把当前结果写成已完成视觉验收。
- 本轮真实模型调用 0、API 费用 0 元。下一步做 mock 浏览器回归和基本流程验收，再处理真实样本中的质量策略缺口。

## 2026-09-20 阶段二第三项：浏览器基本流程验收

- 新增 mock 浏览器端到端验收：后端返回嵌套 `validation_result` 后，聊天页实际显示“质量校验：暂不建议发布”、`2 个阻断问题，1 个提醒`、`EV-05` 及整改建议；Chromium 1 项通过（5.7 秒）。提交 `4c4bef27 test: verify evidence validation banner`。
- 首次复测进入登录页，定位为复用的临时开发服务器没有加载测试用 `DEER_FLOW_AUTH_DISABLED=1`，不是质量横幅缺陷；按测试环境重新启动后通过。此前 `page.goto` 超时也由首次编译耗时 34.5 秒超过 30 秒解释，预热后页面 HTTP 200。
- 回归验证：前端全量单元测试 37 个文件、341 项全部通过；TypeScript 与本次相关文件 ESLint 通过。`pnpm test` 被本机 pnpm 的 ignored-builds 安全检查拦截，因此改用项目内已安装的 `rstest` 执行，没有改依赖或批准新的构建脚本。
- 本项只使用模拟接口和本地浏览器，没有访问外部页面、没有调用真实模型、API 费用 0 元。下一步应把真实复测中已确认的 blocker 转成可执行修复项，优先解决字符/工具次数边界与“历史信息混入当前事实”，再做零费用规则回放。

## 2026-09-20 阶段二第四项：当前性规则补洞

- 真实复测中人工发现的“首批 Pro、Plus/Team 随后”被标为 `current_fact`，原校验器只看来源是否被访问，未能识别结论本身是历史叙述；现已增强 EV-01，对“发布时、上线时、首发、首批、当时、曾于”等明确历史语义进行阻断，并提示改成 `historical_fact` 或补当前来源。
- 同时增加误报保护：“系统先检索来源，随后生成报告”属于流程顺序，不会仅因“随后”被当作历史事实。规则不根据页面发布日期自动判定事实过期，无法确定的当前性仍交给人工复核。
- 测试按先失败后修复执行；证据校验相关专项 91 项通过，另含 20 个子测试；Ruff 与 diff-check 通过。提交 `cac0ff0e feat: block historical claims labeled current`。
- 本项没有联网、没有调用真实模型、API 费用 0 元。EV-06 已能按系统真实值阻断 1,079 字符、6 次搜索和 6 次页面查看；下一步不再重复实现计数，而应把阶段二成果整理成一条可演示的产品验收路径和面试材料，再决定是否需要新的付费样本。

## 2026-09-20 AI 产品经理案例材料

- 已创建 `docs/product/AI_PM_PORTFOLIO_CASE_STUDY.md`，使用本项目真实运行、评测与测试数据整理产品定位、问题发现、方案取舍、MVP 状态、三分钟演示、简历写法和面试问答；提交 `618a1574 docs: add AI PM portfolio case study`。
- 文档明确区分合成任务、真实 API 运行和未验证指标，不声称真实用户调研、生产上线或未知样本准确率。下一步推荐先带用户用该文档完成一次项目讲解演练，再根据暴露的理解缺口决定继续优化功能还是申请新的单次真实样本。

## 2026-09-20 阶段三：人工复核发布闭环

- 已新增 Alembic `0004_evidence_reviews`，在 validation 记录中持久化最终状态和追加式 ReviewDecision；人工决定绑定 `validation_id`、`report_hash`、复核人、幂等键、理由和时间。报告哈希变化后旧决定不会作用于新记录。
- 新增受保护的人工复核 API；只有报告所有者可提交。`approved` 仅允许无 blocker 的 `review_required` 报告；退回或拒绝必须填写理由；同一幂等键重复提交返回同一结果，不同请求不能复用。
- 聊天页已提供“确认通过、退回修改、拒绝发布”操作；阻断报告没有确认按钮，拒绝理由会保留在质量卡中。浏览器 3 条核心流程通过：阻断不可确认、批准后变 confirmed、无理由拒绝被阻止且理由提交后可见。
- 验证：人工复核相关后端专项 127 项通过并含 20 个子测试；数据库升级/旧库/并发启动 30 项包含在内；前端 37 个文件、343 项单元测试通过，TypeScript、ESLint、Ruff 和 diff-check 通过。
- 本阶段只使用本地测试数据库和模拟浏览器接口，真实模型调用 0、API 费用 0 元。当前仍是所有者自审 MVP，不等同于企业独立审核、多人会签或生产审批系统；尚未在真实登录会话中对持久化 API 与界面做一次联合验收。
