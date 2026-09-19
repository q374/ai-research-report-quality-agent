# Evidence Validation Shadow Mode Implementation Plan

> **执行方式：** 使用 `superpowers:executing-plans` 在当前任务中逐项执行；不用子智能体。每一步用复选框（`- [ ]`）跟踪。

**Goal:** 将 B0 确定性证据校验接入 DeerFlow 的真实 run/event 数据，在指定测试账号上持久化影子校验结果，同时不影响原回答、不新增模型调用。

**Architecture:** 把 B0 校验与报告哈希契约提升为 backend 内的单一纯函数实现；Gateway 应用层在 run 完成后收集 RunStore/RunEventStore 的系统事实，调用校验核心并通过新 repository 写入 `evidence_validations` 表。自动回调仅处理允许账号与指定质量配置；受权限保护的手动重放用于既有 run 的零费用验证。

**Tech Stack:** Python 3.12、FastAPI、Pydantic、SQLAlchemy async、Alembic、pytest、现有 DeerFlow RunStore/RunEventStore。

**Spec:** `docs/superpowers/specs/2026-09-19-evidence-validation-shadow-mode-design.md`

## Global Constraints

- 只对服务端允许的测试账号和 `evidence-research-v1` 质量配置启用。
- 不修改 frontend，不影响普通聊天，不改变原 run 状态。
- 不调用模型、不访问外网、不自动重跑，不产生新增 API 费用。
- 系统字符、页面、搜索、工具和 Token 只采用 RunStore/RunEventStore 事实。
- 缺少 Claim/Evidence 时标记 `semantic_evaluation=not_evaluable`，不得伪造语义通过。
- 校验器异常保存安全的 `validator_error`，不得泄露内部异常堆栈。
- 数据库变更必须通过新的 Alembic revision；不修改 `0001_baseline`。
- 保持 harness → app 导入防火墙：`deerflow.*` 不得导入 `app.*`。
- 实际测试账号 ID 只写本机未提交配置，不进入代码、文档、日志或提交。
- 每个 backend 代码阶段同步更新相关 README/CLAUDE，最终只做本地提交，不推送、不发布。

## File Structure

- `backend/packages/harness/deerflow/evaluation/`：唯一校验规则与报告版本契约，无网络、数据库和 app 依赖。
- `backend/packages/harness/deerflow/config/evidence_validation_config.py`：默认关闭的影子运行配置。
- `backend/packages/harness/deerflow/persistence/evidence_validation/`：ORM 与 repository。
- `backend/app/gateway/evidence_validation/collector.py`：把 run/event 转为确定性校验输入，只提取必要事实。
- `backend/app/gateway/evidence_validation/service.py`：启用判断、收集、校验、幂等持久化和异常隔离。
- `backend/app/gateway/evidence_validation/dispatcher.py`：跟踪 run 完成后的后台校验任务并在关停前 drain。
- `backend/app/gateway/routers/evidence_validation.py`：所有者只读查询与手动重放接口。

## Review Focus

1. 旧 run 没有质量配置：自动回调必须跳过；允许账号可用显式 Brief 手动重放，且不得修改原 run metadata。
2. event 缺失、截断或最终回答为空：不能把 0 当成真实完成数据，必须保存 `not_evaluable` 或 `validator_error`。
3. 自动回调与手动重放并发：同一 `(run_id, report_hash)` 最终只能有一条记录。
4. 其他用户猜中 thread/run ID：查询和重放均返回 404，不能泄露记录是否存在。
5. 收集、校验或写库失败：原 run 必须保持 `success`，SSE 结束事件不能被延迟或改写。

---

### Task 1: 提升 B0 校验核心为 backend 单一实现

**Files:**
- Create: `backend/packages/harness/deerflow/evaluation/__init__.py`
- Create: `backend/packages/harness/deerflow/evaluation/evidence_validator.py`
- Create: `backend/packages/harness/deerflow/evaluation/evidence_review_workflow.py`
- Modify: `scripts/evidence_validator.py`
- Modify: `scripts/evidence_review_workflow.py`
- Create: `backend/tests/test_evidence_evaluation_core.py`
- Test: `tests/product/test_evidence_validator.py`
- Test: `tests/product/test_evidence_review_workflow.py`

**Interfaces:**
- Produces: `validate(payload: dict) -> dict`
- Produces: `canonicalize_url(url: str) -> str`
- Produces: `build_validation_record(payload: dict, *, thread_id: str, run_id: str, message_id: str, owner_user_id: str, validator_func=validate, now: str | None=None) -> dict`
- Produces: `submit_review(...) -> dict`、`refresh_validation_record(...) -> dict`
- Compatibility: 根目录两个 `scripts/*.py` 仅转发上述接口，CLI 行为保持不变。

- [ ] **Step 1: 写 backend 导入与兼容性失败测试**

```python
def test_backend_core_matches_legacy_entrypoint():
    from deerflow.evaluation.evidence_validator import validate as backend_validate
    from scripts.evidence_validator import validate as legacy_validate

    payload = load_fixture("t001_v3")
    assert backend_validate(payload) == legacy_validate(payload)


def test_automatic_validator_cannot_confirm():
    record = build_validation_record(
        clean_payload(),
        thread_id="t1", run_id="r1", message_id="m1", owner_user_id="u1",
        validator_func=lambda _: {"status": "confirmed", "findings": [], "metrics": {}},
    )
    assert record["final_status"] == "validator_error"
```

- [ ] **Step 2: 运行测试并确认 RED**

Run:

```powershell
cd backend
$env:PYTHONPATH='.'
uv run pytest tests/test_evidence_evaluation_core.py -v
```

Expected: 因 `deerflow.evaluation` 不存在而导入失败。

- [ ] **Step 3: 迁移纯函数并建立薄包装器**

将现有两个脚本的规则和工作流原样移动到 `deerflow.evaluation`。根目录脚本只负责：

```python
HARNESS_SRC = Path(__file__).resolve().parents[1] / "backend" / "packages" / "harness"
sys.path.insert(0, str(HARNESS_SRC))
from deerflow.evaluation.evidence_validator import canonicalize_url, main, validate
```

工作流包装器也必须写成明确的薄转发，不保留第二套逻辑：

```python
from deerflow.evaluation.evidence_review_workflow import (
    build_validation_record,
    main,
    refresh_validation_record,
    submit_review,
)
```

- [ ] **Step 4: 运行 backend 与 B0 回归**

Run:

```powershell
cd backend
$env:PYTHONPATH='.'
uv run pytest tests/test_evidence_evaluation_core.py -v
cd ..
python -m unittest discover -s tests/product -p 'test_*.py' -v
python scripts/replay_evidence_validation.py tests/product/fixtures/b0_manifest.json
```

Expected: backend 新测试通过；产品测试全部通过；回放仍为 `8 samples, false_releases=0, false_blocks=0, mismatches=0`。

- [ ] **Step 5: 提交**

```powershell
git add backend/packages/harness/deerflow/evaluation scripts/evidence_validator.py scripts/evidence_review_workflow.py backend/tests/test_evidence_evaluation_core.py
git commit -m "refactor: promote evidence validation core"
```

---

### Task 2: 增加默认关闭的影子配置

**Files:**
- Create: `backend/packages/harness/deerflow/config/evidence_validation_config.py`
- Modify: `backend/packages/harness/deerflow/config/app_config.py`
- Modify: `config.example.yaml`
- Create: `backend/tests/test_evidence_validation_config.py`

**Interfaces:**
- Produces: `EvidenceValidationConfig(enabled: bool=False, quality_profile_ids: list[str], allowed_user_ids: list[str])`
- Produces: `EvidenceValidationConfig.is_allowed(*, user_id: str | None, quality_profile_id: str | None) -> bool`
- AppConfig field: `evidence_validation: EvidenceValidationConfig`

- [ ] **Step 1: 写配置失败测试**

```python
def test_shadow_validation_is_disabled_by_default():
    config = EvidenceValidationConfig()
    assert config.enabled is False
    assert config.is_allowed(user_id="u1", quality_profile_id="evidence-research-v1") is False


def test_requires_both_allowed_user_and_profile():
    config = EvidenceValidationConfig(
        enabled=True,
        allowed_user_ids=["u1"],
        quality_profile_ids=["evidence-research-v1"],
    )
    assert config.is_allowed(user_id="u1", quality_profile_id="evidence-research-v1") is True
    assert config.is_allowed(user_id="u2", quality_profile_id="evidence-research-v1") is False
    assert config.is_allowed(user_id="u1", quality_profile_id="ordinary-chat") is False
```

同时断言 `config.example.yaml` 的 `config_version` 从 14 升到 15，示例 `allowed_user_ids` 为空。

- [ ] **Step 2: 运行测试并确认 RED**

Run:

```powershell
cd backend
$env:PYTHONPATH='.'
uv run pytest tests/test_evidence_validation_config.py -v
```

Expected: 配置模块或 AppConfig 字段不存在。

- [ ] **Step 3: 实现最小配置**

```python
class EvidenceValidationConfig(BaseModel):
    enabled: bool = False
    quality_profile_ids: list[str] = Field(default_factory=lambda: ["evidence-research-v1"])
    allowed_user_ids: list[str] = Field(default_factory=list)

    def is_allowed(self, *, user_id: str | None, quality_profile_id: str | None) -> bool:
        return (
            self.enabled
            and bool(user_id)
            and user_id in self.allowed_user_ids
            and bool(quality_profile_id)
            and quality_profile_id in self.quality_profile_ids
        )
```

`config.example.yaml` 只写空允许列表，绝不写真实账号 ID。

- [ ] **Step 4: 运行配置测试与配置解析回归**

Run:

```powershell
cd backend
$env:PYTHONPATH='.'
uv run pytest tests/test_evidence_validation_config.py tests/test_app_config.py -v
```

Expected: 全部通过。

- [ ] **Step 5: 提交**

```powershell
git add backend/packages/harness/deerflow/config/evidence_validation_config.py backend/packages/harness/deerflow/config/app_config.py config.example.yaml backend/tests/test_evidence_validation_config.py
git commit -m "feat: add evidence validation shadow config"
```

---

### Task 3: 持久化 EvidenceValidationRecord

**Files:**
- Create: `backend/packages/harness/deerflow/persistence/evidence_validation/__init__.py`
- Create: `backend/packages/harness/deerflow/persistence/evidence_validation/model.py`
- Create: `backend/packages/harness/deerflow/persistence/evidence_validation/sql.py`
- Modify: `backend/packages/harness/deerflow/persistence/models/__init__.py`
- Create: `backend/packages/harness/deerflow/persistence/migrations/versions/0003_evidence_validations.py`
- Modify: `backend/tests/test_persistence_bootstrap.py`
- Modify: `backend/tests/test_persistence_bootstrap_concurrency.py`
- Modify: `backend/tests/test_persistence_bootstrap_regression.py`
- Create: `backend/tests/test_evidence_validation_repository.py`

**Interfaces:**
- Produces: `EvidenceValidationRepository(session_factory)`
- Produces: `upsert(record: dict) -> dict`
- Produces: `get_by_run(thread_id: str, run_id: str, *, user_id=AUTO) -> dict | None`
- Database uniqueness: `(run_id, report_hash)`。

- [ ] **Step 1: 写 repository 和迁移失败测试**

```python
@pytest.mark.anyio
async def test_upsert_is_idempotent(session_factory):
    repo = EvidenceValidationRepository(session_factory)
    first = await repo.upsert(sample_record())
    second = await repo.upsert(sample_record())
    assert first["validation_id"] == second["validation_id"]
    assert await count_rows(session_factory, "evidence_validations") == 1


@pytest.mark.anyio
async def test_concurrent_upsert_returns_one_record(session_factory):
    repo = EvidenceValidationRepository(session_factory)
    first, second = await asyncio.gather(
        repo.upsert(sample_record()),
        repo.upsert(sample_record()),
    )
    assert first["validation_id"] == second["validation_id"]
    assert await count_rows(session_factory, "evidence_validations") == 1


@pytest.mark.anyio
async def test_get_by_run_enforces_owner(session_factory):
    repo = EvidenceValidationRepository(session_factory)
    await repo.upsert(sample_record(user_id="u1"))
    assert await repo.get_by_run("t1", "r1", user_id="u1") is not None
    assert await repo.get_by_run("t1", "r1", user_id="u2") is None
```

把 bootstrap 测试的 HEAD 常量更新为 `0003_evidence_validations`，并断言升级后新表存在且 `0001_baseline` 未新增该表。

- [ ] **Step 2: 运行测试并确认 RED**

Run:

```powershell
cd backend
$env:PYTHONPATH='.'
uv run pytest tests/test_evidence_validation_repository.py tests/test_persistence_bootstrap.py -v
```

Expected: repository、ORM 或 0003 migration 不存在。

- [ ] **Step 3: 实现 ORM、repository 与 migration**

ORM 使用 JSON 列保存 `source_payload_json` 与 `validation_result_json`，使用字符串列保存身份、状态和 hash；`created_at/updated_at` 使用 UTC。repository 的 upsert 先按 `(run_id, report_hash)` 查询，存在即返回；并发插入若触发唯一约束，则回滚该事务并重新查询既有记录。任何路径都不得覆盖历史记录。

Migration 必须：

```python
revision = "0003_evidence_validations"
down_revision = "0002_runs_token_usage"
```

并创建唯一约束 `uq_evidence_validations_run_hash` 及 user/thread/run 索引。

- [ ] **Step 4: 验证 migration、并发幂等和重启读取**

Run:

```powershell
cd backend
$env:PYTHONPATH='.'
uv run pytest tests/test_evidence_validation_repository.py tests/test_persistence_bootstrap.py tests/test_persistence_bootstrap_concurrency.py tests/test_persistence_bootstrap_regression.py -v
```

Expected: 全部通过；临时 SQLite 关闭并重新打开后仍能读到记录。

- [ ] **Step 5: 提交**

```powershell
git add backend/packages/harness/deerflow/persistence/evidence_validation backend/packages/harness/deerflow/persistence/models/__init__.py backend/packages/harness/deerflow/persistence/migrations/versions/0003_evidence_validations.py backend/tests/test_evidence_validation_repository.py backend/tests/test_persistence_bootstrap.py backend/tests/test_persistence_bootstrap_concurrency.py backend/tests/test_persistence_bootstrap_regression.py
git commit -m "feat: persist evidence validation records"
```

---

### Task 4: 收集真实 run/event 并生成影子记录

**Files:**
- Create: `backend/app/gateway/evidence_validation/__init__.py`
- Create: `backend/app/gateway/evidence_validation/collector.py`
- Create: `backend/app/gateway/evidence_validation/service.py`
- Create: `backend/tests/test_evidence_validation_collector.py`
- Create: `backend/tests/test_evidence_validation_service.py`

**Interfaces:**
- Consumes: `RunStore.get(run_id, user_id=None)`、`RunEventStore.list_events(thread_id, run_id, limit=500)`、Task 1 `build_validation_record`、Task 3 repository。
- Produces: `collect_shadow_payload(run: dict, events: list[dict], *, brief: dict, quality_profile_id: str, source: str) -> tuple[dict, str, str]`
- Produces: `ShadowValidationService(run_store, event_store, repository, config_provider, record_builder=build_validation_record)`，以可注入 `record_builder` 隔离确定性校验异常测试。`process_run(*, thread_id: str, run_id: str, owner_user_id: str, quality_profile_id: str | None=None, brief: dict | None=None, source: Literal["auto", "manual_replay"]="auto") -> dict | None`

- [ ] **Step 1: 写 collector 失败测试**

测试使用固定 run/event 字典，必须覆盖：

```python
def test_collector_uses_system_facts_not_model_self_report():
    payload, semantic_state, message_id = collect_shadow_payload(
        run={"run_id": "r1", "last_ai_message": "实际正文", "total_tokens": 120, "llm_call_count": 2},
        events=[
            {"seq": 1, "event_type": "ai_message", "category": "message", "content": "实际正文"},
            {"seq": 2, "event_type": "llm.tool.result", "category": "message", "content": {"name": "web_search", "content": "https://example.com/a"}},
        ],
        brief=valid_brief(max_chars=4),
        quality_profile_id="evidence-research-v1",
        source="manual_replay",
    )
    assert payload["report"]["rendered_text"] == "实际正文"
    assert payload["report"]["token_usage"]["total_tokens"] == 120
    assert payload["report"]["observed_searches"] == 1
    assert semantic_state == "not_evaluable"
```

同时测试：URL 锚点重复保留页面查看次数但规范化唯一页；截断事件设置 `audit.data_gaps`；空最终回答产生明确缺口而非“0 字通过”；collector 不保存工具的完整敏感参数。

- [ ] **Step 2: 运行 collector 测试并确认 RED**

Run:

```powershell
cd backend
$env:PYTHONPATH='.'
uv run pytest tests/test_evidence_validation_collector.py -v
```

Expected: collector 模块不存在。

- [ ] **Step 3: 实现最小 collector**

实现要求：

- 最终正文优先采用 `run.last_ai_message`，并记录与最后 `ai_message` event 是否一致。
- 只从已知 `llm.tool.result` 的结构化 `name/content/artifact` 中提取工具名和 HTTP(S) URL。
- 搜索计数只认明确搜索工具名集合；页面计数只认明确读取/抓取工具名集合。
- 无法可靠分类的工具只进入 `used_tools`，不冒充搜索或页面。
- Claim/Evidence 只接受 run metadata 或手动 Brief 附带的结构化对象；缺失时使用空列表并返回 `not_evaluable`。
- `audit.human_review` 固定为 `pending`，自动流程不能产生 confirmed。

- [ ] **Step 4: 写 service 失败测试**

```python
@pytest.mark.anyio
async def test_ineligible_run_is_skipped(service):
    result = await service.process_run(
        thread_id="t1", run_id="r1", owner_user_id="u2", source="auto"
    )
    assert result is None
    assert service.repository.upsert.await_count == 0


@pytest.mark.anyio
async def test_validation_failure_does_not_change_run_status(service):
    service.record_builder.side_effect = RuntimeError("internal secret")
    result = await service.process_run(
        thread_id="t1", run_id="r1", owner_user_id="u1",
        quality_profile_id="evidence-research-v1", brief=valid_brief(), source="manual_replay",
    )
    assert result["auto_status"] == "validator_error"
    assert "internal secret" not in json.dumps(result)
    assert service.run_store.update_status.await_count == 0
```

还要测试：run 非 success 跳过；thread/run 不匹配拒绝；自动模式必须读取 metadata profile；手动模式不得修改 metadata；重复处理返回同一 validation_id。

- [ ] **Step 5: 实现 service 并运行专项测试**

Run:

```powershell
cd backend
$env:PYTHONPATH='.'
uv run pytest tests/test_evidence_validation_collector.py tests/test_evidence_validation_service.py -v
```

Expected: 全部通过；异常文本不进入返回数据。

- [ ] **Step 6: 提交**

```powershell
git add backend/app/gateway/evidence_validation backend/tests/test_evidence_validation_collector.py backend/tests/test_evidence_validation_service.py
git commit -m "feat: build shadow validation records from runs"
```

---

### Task 5: 接入依赖、完成回调和受保护 API

**Files:**
- Create: `backend/app/gateway/evidence_validation/dispatcher.py`
- Create: `backend/app/gateway/routers/evidence_validation.py`
- Modify: `backend/app/gateway/deps.py`
- Modify: `backend/app/gateway/app.py`
- Modify: `backend/app/gateway/services.py`
- Create: `backend/tests/test_evidence_validation_api.py`
- Create: `backend/tests/test_evidence_validation_dispatcher.py`
- Modify: `backend/tests/test_gateway_run_drain_shutdown.py`

**Interfaces:**
- Produces: `ShadowValidationDispatcher.schedule(record: RunRecord) -> None`
- Produces: `ShadowValidationDispatcher.drain(timeout: float=5.0) -> None`
- Route: `GET /api/threads/{thread_id}/runs/{run_id}/evidence-validation`
- Route: `POST /api/threads/{thread_id}/runs/{run_id}/evidence-validation/replay`
- Replay body: `quality_profile_id: str` 和完整 ResearchBrief 字段。

- [ ] **Step 1: 写 API 权限与重放失败测试**

```python
def test_other_owner_gets_404(client_user_b, seeded_user_a_record):
    response = client_user_b.get("/api/threads/t-a/runs/r-a/evidence-validation")
    assert response.status_code == 404


def test_manual_replay_is_idempotent(client_user_a, valid_brief):
    first = client_user_a.post(
        "/api/threads/t-a/runs/r-a/evidence-validation/replay",
        json={"quality_profile_id": "evidence-research-v1", "brief": valid_brief},
    )
    second = client_user_a.post(
        "/api/threads/t-a/runs/r-a/evidence-validation/replay",
        json={"quality_profile_id": "evidence-research-v1", "brief": valid_brief},
    )
    assert first.status_code == second.status_code == 200
    assert first.json()["validation_id"] == second.json()["validation_id"]
```

覆盖 404 未生成、403 非允许账号、409 非 success/不允许 profile、thread/run 不匹配和响应脱敏。

- [ ] **Step 2: 写 dispatcher 失败测试**

```python
@pytest.mark.anyio
async def test_dispatcher_does_not_delay_or_rewrite_completed_run():
    record = success_record()
    dispatcher.schedule(record)
    assert record.status == RunStatus.success
    await dispatcher.drain()
    dispatcher.service.process_run.assert_awaited_once()


@pytest.mark.anyio
async def test_dispatcher_drains_before_database_close():
    dispatcher.schedule(success_record())
    await dispatcher.drain(timeout=1.0)
    assert dispatcher.pending_count == 0
```

- [ ] **Step 3: 运行 API/dispatcher 测试并确认 RED**

Run:

```powershell
cd backend
$env:PYTHONPATH='.'
uv run pytest tests/test_evidence_validation_api.py tests/test_evidence_validation_dispatcher.py -v
```

Expected: router、dispatcher 或 app.state 依赖不存在。

- [ ] **Step 4: 初始化 repository/service/dispatcher**

在 `langgraph_runtime` 中：

1. 初始化共享 session factory。
2. 创建 `EvidenceValidationRepository`。
3. 在 RunEventStore 创建后构造 `ShadowValidationService`。
4. 创建 `ShadowValidationDispatcher` 并存入 `app.state`。
5. finally 中先 drain dispatcher，再关闭数据库 engine。

新增 `get_evidence_validation_repo/service/dispatcher` getter；数据库 backend 为 memory 时保持 feature unavailable，不伪装持久化。

- [ ] **Step 5: 注册完成回调和 API**

`start_run` 在 `record.task` 创建后调用：

```python
dispatcher = get_shadow_validation_dispatcher(request)
dispatcher.schedule(record)
```

Dispatcher 等原 task 完成后读取最终持久化状态，再调用 service；不修改 task 结果。路由沿用现有认证依赖，先按当前用户读取 run；非所有者、run 不存在或 thread/run 不匹配统一返回 404。只有账号和 profile 已在服务端允许列表时才能重放。

- [ ] **Step 6: 运行专项和核心回归**

Run:

```powershell
cd backend
$env:PYTHONPATH='.'
uv run pytest tests/test_evidence_validation_api.py tests/test_evidence_validation_dispatcher.py tests/test_gateway_run_drain_shutdown.py tests/test_owner_isolation.py tests/test_feedback.py -v
```

Expected: 全部通过；其他用户请求为 404；run success 不变。

- [ ] **Step 7: 提交**

```powershell
git add backend/app/gateway/evidence_validation/dispatcher.py backend/app/gateway/routers/evidence_validation.py backend/app/gateway/deps.py backend/app/gateway/app.py backend/app/gateway/services.py backend/tests/test_evidence_validation_api.py backend/tests/test_evidence_validation_dispatcher.py backend/tests/test_gateway_run_drain_shutdown.py
git commit -m "feat: connect evidence validation shadow mode"
```

---

### Task 6: 文档、全量验证和已有 run 零费用验收

**Files:**
- Modify: `README.md`
- Modify: `backend/CLAUDE.md`
- Modify: `docs/product/STAGE_B_INTEGRATION_REVIEW.md`
- Create: `docs/product/evidence-validator-results/B1_SHADOW_ACCEPTANCE.md`
- Modify: `MEMORY.md`
- Local-only: `config.yaml`（只加入真实测试账号 ID，不提交）

**Interfaces:**
- Consumes: Tasks 1—5 的 API、迁移和服务。
- Produces: B1 实际测试证据、零新增模型调用结论、用户学习入口。

- [ ] **Step 1: 更新正式文档**

README/CLAUDE 必须写明：

- 功能默认关闭；
- 如何配置允许账号和 profile；
- 自动与手动重放差异；
- 影子模式不影响主回答；
- 语义输入不足显示 `not_evaluable`；
- GET/POST 接口与权限；
- migration `0003_evidence_validations`。

产品文档只记录实际完成项，不提前写“真实 run 已通过”。

- [ ] **Step 2: 执行静态和测试验收**

Run:

```powershell
cd backend
$env:PYTHONPATH='.'
uv run ruff check app packages/harness/deerflow tests/test_evidence_*.py
uv run pytest tests/test_evidence_evaluation_core.py tests/test_evidence_validation_config.py tests/test_evidence_validation_repository.py tests/test_evidence_validation_collector.py tests/test_evidence_validation_service.py tests/test_evidence_validation_api.py tests/test_evidence_validation_dispatcher.py -v
uv run pytest tests/test_persistence_bootstrap.py tests/test_persistence_bootstrap_concurrency.py tests/test_persistence_bootstrap_regression.py tests/test_harness_boundary.py tests/test_owner_isolation.py tests/test_gateway_run_drain_shutdown.py -v
uv run pytest tests/ -v
cd ..
python -m unittest discover -s tests/product -p 'test_*.py' -v
python scripts/replay_evidence_validation.py tests/product/fixtures/b0_manifest.json
python -m compileall -q backend/app/gateway/evidence_validation backend/packages/harness/deerflow/evaluation backend/packages/harness/deerflow/persistence/evidence_validation
git diff --check
```

Expected: 专项测试和 backend 全量测试全部通过；B0 仍为 8 样本零不一致；检查 `git diff` 后确认没有真实账号 ID、密钥或完整敏感工具参数。

- [ ] **Step 3: 构建并启动本机 gateway**

先核对 Docker 资源和现有容器，不恢复 Dify。只重建受影响的 gateway 镜像并保留 frontend/nginx。启动后验证：

```text
GET http://localhost:2026/health -> HTTP 200
GET http://localhost:2026/openapi.json -> 包含 evidence-validation 两个路径
```

不得发送新 DeerFlow 消息。

- [ ] **Step 4: 对已有成功 run 执行手动重放**

使用当前登录测试账号，在 Swagger 或同源接口中选择一条已有 success run，提交：

```json
{
  "quality_profile_id": "evidence-research-v1",
  "brief": {
    "task_id": "existing-run-shadow-replay",
    "required_dimensions": [],
    "allowed_domains": [],
    "time_scope": "existing-record",
    "max_searches": 10,
    "max_pages": 20,
    "max_chars": 2000,
    "forbidden_tools": []
  }
}
```

先记录调用前 run 的 Token 与模型调用数；重放后再次读取并证明两者未增加。核对记录绑定真实 user/thread/run/report_hash，且 `source=manual_replay`、`semantic_evaluation=not_evaluable`（若旧 run 没有结构化 Claim/Evidence）。

- [ ] **Step 5: 验证持久化与权限**

重启 gateway 后再次 GET 同一记录，validation_id 与 report_hash 必须保持一致。使用不存在或其他用户上下文请求时必须返回 404。若无法安全获得第二用户会话，只报告“自动化权限测试通过，未进行第二真实账号手工验证”，不得伪称完成。

- [ ] **Step 6: 记录真实验收与学习材料**

`B1_SHADOW_ACCEPTANCE.md` 必须包含：

- run/thread 标识与脱敏用户标识；
- 系统字符、页面、搜索、工具、Token；
- 自动状态和 `semantic_evaluation`；
- 重启前后 validation_id；
- 新增模型调用 0 的证据；
- 仍未验证的语义映射、真实用户价值和生产稳定性。

MEMORY 更新当前分支、提交、验证范围、运行状态和下一步用户教学入口。

- [ ] **Step 7: 最终提交**

```powershell
git add README.md backend/CLAUDE.md docs/product/STAGE_B_INTEGRATION_REVIEW.md docs/product/evidence-validator-results/B1_SHADOW_ACCEPTANCE.md MEMORY.md
git commit -m "docs: record b1 shadow validation acceptance"
```

不要 `git add config.yaml`，不要推送或发布。
