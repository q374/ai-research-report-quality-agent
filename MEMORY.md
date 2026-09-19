# 产品项目记忆

更新时间：2026-09-19

- 当前目标：DeerFlow 原版与 DeepSeek 已跑通，正在用合成题集学习并验证证据优先产品情报 Agent；产品功能开发尚未开始。
- 目录：D:\AI产品经理简历\项目经历\product-intelligence-agent。
- 基线：v2.0.0 / 7e7f0410797693cf882594555ba414e0361d4c6f；开发分支 codex/product-intelligence-mvp。origin 与 upstream 均指向官方仓库，不推送。
- 迁移验证：1388 个文件，除路径检查自动更新的 .git/index 缓存外 SHA256 一致；索引 ls-files --stage 一致；git fsck --full 通过。原版源码未改动。
- 本目录新增 AGENTS.md、MEMORY.md 为项目规则与状态，不是产品功能。
- 运行入口：Install.md、Makefile、scripts/docker.sh、docker/docker-compose-dev.yaml。backend/frontend 子目录规则按需读取。
- 当前运行：Docker 上的 frontend、gateway、nginx 健康；Dify 容器保持停止，避免同时占用内存。DeepSeek Flash 已完成基础对话和 T001 联网评测。
- 当前评测：T001 已执行并判定“需改进”；未获新的费用授权前不重跑 T001、不执行 T002。
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
