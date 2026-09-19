# Evidence Validator B0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立不接入真实回答链路的 B0 可执行契约、固定样本回放和静态人工复核界面原型。

**Architecture:** 保留 `scripts/evidence_validator.py` 作为确定性校验核心；新增独立工作流模块负责校验记录、报告哈希、权限和人工决定；新增离线回放器汇总三份负样本与五份正向/边界样本；最后由纯函数渲染静态 HTML 原型。所有输入均来自本地夹具，不联网、不调用模型、不修改 DeerFlow backend/frontend。

**Tech Stack:** Python 3 标准库、`unittest`、静态 HTML/CSS/JavaScript。

**Spec:** `docs/product/STAGE_B_INTEGRATION_REVIEW.md`

## Global Constraints

- 不接入真实回答链路，不修改 DeerFlow `backend/`、`frontend/`。
- 不联网、不调用模型、不产生 API 费用。
- 普通聊天不受影响。
- 系统观测事实不能采用模型自报值。
- 有 blocker 或校验异常时不得人工批准。
- 人工决定必须绑定报告哈希、复核用户和时间。
- 报告、Claim 或 Evidence 变化后，旧批准失效。
- 只做本地提交，不推送、不发布。

## Review Focus

- 非线程所有者提交复核：必须拒绝，且不能追加决定记录。
- 报告批准后正文或证据变化：旧哈希必须失效。
- 校验器抛出异常：生成 `validator_error`，不能伪装为通过。
- blocker 状态提交 approved：必须拒绝。
- 重复提交相同决定：使用幂等键返回同一结果，不重复追加。

---

### Task 1: ValidationRecord 与 ReviewDecision 可执行契约

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/evidence_review_workflow.py`
- Create: `tests/product/test_evidence_review_workflow.py`

**Interfaces:**
- Consumes: `scripts.evidence_validator.validate(payload: dict) -> dict`
- Produces: `build_validation_record(...) -> dict`、`submit_review(...) -> dict`、`refresh_validation_record(...) -> dict`

- [ ] **Step 1: 写失败测试**

测试必须覆盖：记录绑定 thread/run/message/owner；哈希随正文或证据改变；异常变成 `validator_error`；blocked 不能批准；非所有者不能复核；退回/驳回必须有理由；合法批准进入 confirmed；同一幂等键不重复追加。

- [ ] **Step 2: 运行测试并确认 RED**

Run: `python -m unittest tests.product.test_evidence_review_workflow -v`

Expected: 因 `scripts.evidence_review_workflow` 不存在而失败。

- [ ] **Step 3: 实现最小工作流**

`build_validation_record` 对报告正文、claims、evidence 做规范 JSON SHA-256；调用校验器并保存 auto_status。捕获异常时设置 `validator_error`。`submit_review` 验证 owner、report_hash、状态、理由与幂等键，追加不可变决定；`refresh_validation_record` 在内容变化后重建记录并清空旧决定。

- [ ] **Step 4: 运行测试并确认 GREEN**

Run: `python -m unittest tests.product.test_evidence_review_workflow -v`

Expected: 全部通过。

- [ ] **Step 5: 提交**

Commit: `feat: add evidence review workflow contract`

---

### Task 2: 五份正向/边界样本与离线回放

**Files:**
- Create: `tests/product/fixtures/b0_clean_current.json`
- Create: `tests/product/fixtures/b0_clean_historical.json`
- Create: `tests/product/fixtures/b0_exact_limit.json`
- Create: `tests/product/fixtures/b0_duplicate_urls.json`
- Create: `tests/product/fixtures/b0_neutral_review.json`
- Create: `tests/product/fixtures/b0_manifest.json`
- Create: `scripts/replay_evidence_validation.py`
- Create: `tests/product/test_evidence_validation_replay.py`
- Create: `docs/product/evidence-validator-results/b0-replay.json`
- Create: `docs/product/evidence-validator-results/B0_REPLAY_SUMMARY.md`

**Interfaces:**
- Consumes: `scripts.evidence_validator.validate`、Task 1 `build_validation_record`
- Produces: `replay_manifest(manifest_path: Path) -> dict`

- [ ] **Step 1: 写失败测试和固定夹具**

清单包含原三份负样本和五份正向/边界样本。测试断言：3 份负样本均 blocked；5 份新样本均 review_required；总计 8；错误放行 0；错误阻断 0；exact-limit 正好 800 字符；duplicate-urls 保留 2 次查看但唯一页为 1。

- [ ] **Step 2: 运行测试并确认 RED**

Run: `python -m unittest tests.product.test_evidence_validation_replay -v`

Expected: 因回放器不存在而失败。

- [ ] **Step 3: 实现回放器**

读取 manifest 的字面期望，调用真实校验器，输出逐样本状态、规则、字符、页面统计与汇总；出现期望不一致时 CLI 返回非零。

- [ ] **Step 4: 运行测试并确认 GREEN，生成结果**

Run: `python -m unittest tests.product.test_evidence_validation_replay -v`

Expected: 全部通过。

Run: `python scripts/replay_evidence_validation.py tests/product/fixtures/b0_manifest.json --output docs/product/evidence-validator-results/b0-replay.json`

Expected: `8 samples, 0 false releases, 0 false blocks`。

- [ ] **Step 5: 更新结果摘要并提交**

Commit: `test: add b0 evidence validation replay set`

---

### Task 3: 静态人工复核界面原型

**Files:**
- Create: `scripts/render_evidence_review_prototype.py`
- Create: `tests/product/test_evidence_review_prototype.py`
- Create: `docs/product/prototypes/evidence-review/index.html`
- Create: `docs/product/prototypes/evidence-review/README.md`

**Interfaces:**
- Consumes: Task 1 ValidationRecord、Task 2 回放结果
- Produces: `render_review_page(records: list[dict]) -> str`

- [ ] **Step 1: 写失败测试**

测试断言：blocked 卡片显示“不可发布”且批准按钮 disabled；review_required 显示“待人工复核”且批准可用；confirmed 显示复核人和时间；validator_error 显示“校验异常”且批准 disabled；页面包含报告陈述、证据原文、校验发现、人工动作四区；HTML 不包含密钥。

- [ ] **Step 2: 运行测试并确认 RED**

Run: `python -m unittest tests.product.test_evidence_review_prototype -v`

Expected: 因渲染器不存在而失败。

- [ ] **Step 3: 实现最小渲染器并生成 HTML**

使用语义化 HTML、响应式 CSS 和少量本地 JavaScript 展示四种状态。数据全部嵌入本地文件；交互只用于切换样本和打开/关闭证据抽屉，不提交网络请求。

- [ ] **Step 4: 运行测试并确认 GREEN**

Run: `python -m unittest tests.product.test_evidence_review_prototype -v`

Expected: 全部通过。

- [ ] **Step 5: 浏览器验证**

用本地 HTTP 服务打开原型；检查桌面和窄屏，切换四种状态，确认 blocker 和 validator_error 均不能批准。保存截图到 `docs/product/prototypes/evidence-review/`。

- [ ] **Step 6: 提交**

Commit: `feat: add evidence review ui prototype`

---

### Task 4: 总体验收与项目记忆

**Files:**
- Modify: `docs/product/STAGE_B_INTEGRATION_REVIEW.md`
- Modify: `docs/product/EVIDENCE_VALIDATOR_SPEC.md`
- Modify: `docs/product/PRODUCT_OPPORTUNITY.md`
- Modify: `MEMORY.md`

**Interfaces:**
- Consumes: Tasks 1—3 的实际测试、回放和浏览器证据
- Produces: B0 真实完成状态、未验证项和下一决策门槛

- [ ] **Step 1: 运行完整产品测试**

Run: `python -m unittest discover -s tests/product -p "test_*.py" -v`

Expected: 全部通过、0 failures、0 errors。

- [ ] **Step 2: 静态与数据检查**

Run: Python 编译、JSON 解析、`git diff --check`、敏感信息扫描。

Expected: 全部通过，无密钥模式命中。

- [ ] **Step 3: 更新文档和 MEMORY**

只写真实结果；区分离线回放、静态原型和真实链路未接入。

- [ ] **Step 4: 最终复核并提交**

Commit: `docs: record evidence validator b0 acceptance`

最终不推送、不发布、不运行模型。
