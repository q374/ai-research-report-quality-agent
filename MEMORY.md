# 产品项目记忆

更新时间：2026-09-18

- 当前目标：先安全迁移，再接通 DeepSeek 并跑通 DeerFlow 原版；产品功能开发尚未开始。
- 目录：D:\AI产品经理简历\项目经历\product-intelligence-agent。
- 基线：v2.0.0 / 7e7f0410797693cf882594555ba414e0361d4c6f；开发分支 codex/product-intelligence-mvp。origin 与 upstream 均指向官方仓库，不推送。
- 迁移验证：1388 个文件，除路径检查自动更新的 .git/index 缓存外 SHA256 一致；索引 ls-files --stage 一致；git fsck --full 通过。原版源码未改动。
- 本目录新增 AGENTS.md、MEMORY.md 为项目规则与状态，不是产品功能。
- 运行入口：Install.md、Makefile、scripts/docker.sh、docker/docker-compose-dev.yaml。backend/frontend 子目录规则按需读取。
- 配置、依赖、模型连通性和服务均未验收；无本任务实际 API 支出，跨项目累计费用未核实。密钥未接收，不得声称模型已接通。
- 后续先检查 D 盘依赖/缓存落点与 Docker 磁盘位置，避免源码迁移后镜像构建继续挤占 C 盘；安全输入密钥并在确认的预算范围内做最小调用。
- 产品规格沿用学习记忆的 2026-09-18 接续决策；完成原版体验后再细化 MVP，保留真实性与人工验收门禁。
