# B1.1 Persistent Evidence Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让证据研究 run 跨重启保存真实工具事件，并在同一研究运行中提交可点击、可定位的 Claim/Evidence 候选，供 B1 影子校验器做确定性核对。

**Architecture:** 复用现有 SQL `run_events` 与 B1 `evidence_validations`，不新建事件数据库。只有通过账号/profile/ResearchBrief 三重资格检查的 run 才获得 `submit_evidence_report` 直接结束工具；工具在一次最终模型响应中提交 Markdown、Claim 和 Evidence，RunJournal 持久化专用事件，采集器再用真实工具事件补全采集状态并调用兼容旧夹具的确定性校验器。

**Tech Stack:** Python 3.12、FastAPI、Pydantic、LangChain/LangGraph、SQLAlchemy/SQLite、pytest、Ruff、Next.js/React、Rstest、Playwright。

**Spec:** `docs/superpowers/specs/2026-09-19-persistent-evidence-contract-design.md`

## Global Constraints

- 功能继续默认关闭，只允许 `EvidenceValidationConfig.is_allowed()` 通过的账号和 `evidence-research-v1`。
- 普通聊天、未允许账号、缺少 profile 或缺少 ResearchBrief 的 run 不得看到结构化结束工具。
- Tasks 1—7 不调用真实模型、不联网生成样本、不运行 T002；真实付费样本必须在本计划完成后重新获得单次授权。
- 不调用第二个评分模型；必须用假模型集成测试证明 `submit_evidence_report` 后没有第二次模型响应。
- 本阶段不设置 Claim、Evidence、摘录或 Token 的产品硬上限；测试必须证明超过先前讨论数量仍可通过契约解析。
- Agent 只能提交候选关系，不能提交 `confirmed`；系统采集状态和人工语义状态必须分开。
- 复用现有 `run_events` 与 `evidence_validations` 表，不增加数据库迁移；`config.yaml` 仅本机修改且不得提交。
- 事件、日志和文档不得包含密钥、完整真实用户 ID、带凭据的 URL 或完整敏感工具参数。
- 影子校验失败不得修改原回答或 run status；数据不足时 fail-closed 到 `not_evaluable` / review，而不是伪造通过。
- 保持 B0 旧夹具兼容；旧 `status` 字段仍按原规则回放，新 live contract 使用 `collection_status` + `review_status`。
- 不升级依赖、不推送、不发布。

## Review Focus

1. `return_direct` 只产生 ToolMessage、前端没有最终 AI 气泡，或工具后又发生一次模型调用——Task 2 用真实 `create_agent` + 假模型钉住最终消息与调用次数。
2. 客户端伪造 metadata 后，未允许用户或缺少 ResearchBrief 仍获得工具——Task 3 覆盖账号、profile、brief 和普通聊天四种拒绝路径。
3. Evidence URL 或 Markdown 引用携带 token/userinfo 并被原样持久化——Task 1 覆盖 URL 与可见 Markdown 双重脱敏，Task 5 再覆盖事件采集。
4. 同一 run 出现多个、格式错误或 message_id 不匹配的结构化事件——Task 5 明确选择规则并产生 data gap，不静默猜测。
5. SQLite 写入尚未 flush 就触发影子校验，或重启/所有者过滤后读不到事件——Task 4 和 Task 6 覆盖 flush、重建 store、owner isolation 与调度顺序。

---

## Execution Preflight

在 Task 1 修改任何产品代码前：

```powershell
git status --short
git rev-parse HEAD
cd backend
$env:PYTHONPATH='.'
uv run pytest tests/ -q
cd ..
```

把 base commit、工作区状态、passed/failed/skipped 和失败名称写入本计划对应的本地 SDD ledger。已知 Windows 失败不能当作 B1.1 引入；如果工作区不干净或基线与 B1 验收明显冲突，先核对原因，不覆盖用户修改。

### Task 1: 定义结构化提交契约与安全 URL

**Files:**
- Create: `backend/packages/harness/deerflow/evaluation/evidence_submission.py`
- Modify: `backend/packages/harness/deerflow/evaluation/__init__.py`
- Test: `backend/tests/test_evidence_submission.py`

**Interfaces:**
- Produces: `ClaimCandidate`、`EvidenceCandidate`、`EvidenceReportSubmission`。
- Produces: `sanitize_source_url(value: str) -> str`、`sanitize_citation_links(markdown: str) -> str`、`extract_citation_urls(markdown: str) -> list[str]`。
- Produces: `EvidenceReportSubmission.to_event_payload(message_id: str) -> dict`，固定 `schema_version="2.0"`。

- [ ] **Step 1: 写失败测试锁定契约、无产品上限和脱敏**

```python
def test_submission_accepts_more_than_eight_claims_and_long_excerpt():
    payload = make_submission(
        claims=[make_claim(f"C{i}") for i in range(12)],
        evidence=[make_evidence("E1", excerpt="证" * 500)],
    )
    assert len(EvidenceReportSubmission.model_validate(payload).claims) == 12


def test_evidence_candidate_rejects_agent_confirmed_status():
    with pytest.raises(ValidationError):
        EvidenceCandidate.model_validate({**make_evidence("E1"), "status": "confirmed"})


def test_urls_strip_userinfo_and_sensitive_query_values():
    safe = sanitize_source_url("https://u:p@example.com/doc?token=secret&utm_source=x&id=7#part")
    assert safe == "https://example.com/doc?id=7#part"
    assert "secret" not in sanitize_citation_links(
        "结论。[citation:来源1](https://example.com/doc?api_key=secret&id=7)"
    )
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend; $env:PYTHONPATH='.'; uv run pytest tests/test_evidence_submission.py -v`

Expected: FAIL，模块或类型尚不存在。

- [ ] **Step 3: 实现严格但无数量/长度产品上限的 Pydantic 契约**

```python
class ClaimCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_id: str
    text: str
    claim_type: Literal["current_fact", "historical_fact", "review_question", "unknown"]
    dimension: str
    is_key: bool
    evidence_ids: list[str]
    citation_evidence_ids: list[str]


class EvidenceCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str
    source_url: str
    title: str
    published_at: str | None = None
    excerpt: str
    proposed_relation: Literal["supports", "contradicts", "unclear"]


class EvidenceReportSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rendered_text: str
    claims: list[ClaimCandidate]
    evidence: list[EvidenceCandidate]
```

在 model validator 中对 `source_url` 和 `rendered_text` 的 citation URL 做相同脱敏；只接受 HTTP/HTTPS，不保留 userinfo 和敏感 query key。不得增加 `max_length`、`max_items` 或 Token 阈值。

- [ ] **Step 4: 运行契约与静态检查**

Run:

```powershell
cd backend
$env:PYTHONPATH='.'
uv run pytest tests/test_evidence_submission.py -v
uv run ruff check packages/harness/deerflow/evaluation/evidence_submission.py tests/test_evidence_submission.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add backend/packages/harness/deerflow/evaluation/evidence_submission.py backend/packages/harness/deerflow/evaluation/__init__.py backend/tests/test_evidence_submission.py
git commit -m "feat: define evidence submission contract"
```

---

### Task 2: 实现直接结束工具与可持久化最终消息

**Files:**
- Create: `backend/packages/harness/deerflow/tools/builtins/submit_evidence_report_tool.py`
- Modify: `backend/packages/harness/deerflow/tools/builtins/__init__.py`
- Modify: `backend/packages/harness/deerflow/runtime/journal.py`
- Test: `backend/tests/test_submit_evidence_report_tool.py`
- Test: `backend/tests/test_run_journal.py`

**Interfaces:**
- Produces: `submit_evidence_report_tool`，工具名 `submit_evidence_report`，`return_direct=True`。
- Produces: `RunJournal.record_evidence_report(payload: dict, *, message_id: str) -> None`。
- Command 更新必须依次包含配对 ToolMessage 和带正文的 AIMessage；AIMessage.id 与 evidence event 的 `message_id` 一致。

- [ ] **Step 1: 写工具失败测试**

```python
def test_submit_tool_returns_visible_ai_message_and_records_event():
    journal = Mock()
    runtime = SimpleNamespace(context={"__run_journal": journal}, state={}, config={})
    command = submit_evidence_report_tool.func(
        runtime=runtime,
        tool_call_id="tc-1",
        rendered_text="结论。[citation:来源1](https://example.com/doc)",
        claims=[make_claim("C1")],
        evidence=[make_evidence("E1")],
    )
    tool_message, ai_message = command.update["messages"]
    assert isinstance(tool_message, ToolMessage)
    assert isinstance(ai_message, AIMessage)
    assert ai_message.content.startswith("结论")
    journal.record_evidence_report.assert_called_once()
```

同时增加：journal 缺失时仍返回正文；非法提交不写事件；`RunJournal.on_tool_end(Command)` 把 AIMessage 记为 `ai_message` 而不是 `llm.tool.result`。

- [ ] **Step 2: 写零额外模型响应的假模型集成测试**

用 `_agent_e2e_helpers.FakeToolCallingModel` 或等价 fake model 返回一次 `AIMessage(tool_calls=[submit_evidence_report...])`；通过真实 `langchain.agents.create_agent` 调用工具。断言：

```python
assert model.invocation_count == 1
assert result["messages"][-1].type == "ai"
assert result["messages"][-1].content == rendered_text
assert [m.type for m in result["messages"][-2:]] == ["tool", "ai"]
```

若当前 LangChain 的 `return_direct + Command` 不能满足这四项，停止 Task 2 并回到规格评审；禁止静默增加第二次模型调用或仅返回 ToolMessage。

- [ ] **Step 3: 实现工具和 journal 公共记录方法**

工具使用 `EvidenceReportSubmission.model_validate()`，生成稳定 `message_id=f"evidence-report:{tool_call_id}"`。`record_evidence_report` 写：

```python
self._put(
    event_type="evidence.report.submitted",
    category="outputs",
    content=payload,
    metadata={"message_id": message_id, "schema_version": "2.0"},
)
```

记录失败只写脱敏 debug 日志，不阻断可见回答；缺少事件会在采集阶段变成 data gap。

- [ ] **Step 4: 运行工具、journal 和相邻回归**

Run:

```powershell
cd backend
$env:PYTHONPATH='.'
uv run pytest tests/test_submit_evidence_report_tool.py tests/test_run_journal.py tests/test_tool_args_schema_no_pydantic_warning.py -v
uv run ruff check packages/harness/deerflow/tools/builtins/submit_evidence_report_tool.py packages/harness/deerflow/runtime/journal.py tests/test_submit_evidence_report_tool.py
```

Expected: PASS，fake model 调用数为 1。

- [ ] **Step 5: 提交**

```powershell
git add backend/packages/harness/deerflow/tools/builtins/submit_evidence_report_tool.py backend/packages/harness/deerflow/tools/builtins/__init__.py backend/packages/harness/deerflow/runtime/journal.py backend/tests/test_submit_evidence_report_tool.py backend/tests/test_run_journal.py
git commit -m "feat: add direct evidence report finalizer"
```

---

### Task 3: 按账号、profile 和 ResearchBrief 注入工具

**Files:**
- Create: `backend/packages/harness/deerflow/evaluation/evidence_profile.py`
- Modify: `backend/packages/harness/deerflow/agents/lead_agent/agent.py`
- Test: `backend/tests/test_evidence_profile_agent.py`
- Test: `backend/tests/test_lead_agent_prompt.py`

**Interfaces:**
- Produces: `resolve_evidence_profile(config: RunnableConfig, app_config: AppConfig) -> EvidenceProfileContext | None`。`ResearchBrief` 必须含 `task_id`、`required_dimensions`、`allowed_domains`、`time_scope`、`max_searches`、`max_pages`、`max_chars`、`forbidden_tools`。
- Consumes: `config.context.user_id`、`config.metadata.quality_profile_id`、`config.metadata.research_brief`。
- Produces: profile 专用 Prompt 后缀，要求最终只调用一次 `submit_evidence_report`，引用格式为 `[citation:来源N](URL)`。

- [ ] **Step 1: 写资格矩阵失败测试**

覆盖：

```python
@pytest.mark.parametrize("user,profile,brief,expected", [
    ("allowed", "evidence-research-v1", VALID_BRIEF, True),
    ("other", "evidence-research-v1", VALID_BRIEF, False),
    ("allowed", "other-profile", VALID_BRIEF, False),
    ("allowed", "evidence-research-v1", None, False),
])
def test_submit_tool_visibility(user, profile, brief, expected): ...
```

另外断言 `evidence_validation.enabled=False`、bootstrap agent、普通聊天都没有工具；不得把 `user_id` 写入 system prompt。

- [ ] **Step 2: 运行失败测试**

Run: `cd backend; $env:PYTHONPATH='.'; uv run pytest tests/test_evidence_profile_agent.py tests/test_lead_agent_prompt.py -v`

Expected: 新测试 FAIL。

- [ ] **Step 3: 实现资格解析和 profile 专用注入**

`resolve_evidence_profile` 必须调用现有 `EvidenceValidationConfig.is_allowed()`；ResearchBrief 必须是 mapping 且完整包含上述 8 个字段，列表/整数类型沿用现有 API 契约；不复制用户 ID 到 Prompt。`submit_evidence_report_tool` 在工具策略过滤完成后作为内部 finalizer 注入，不能进入 deferred tool catalog。

Prompt 明确：

```text
仅在完成研究后调用 submit_evidence_report 一次；rendered_text 是用户最终看到的 Markdown。
重要结论使用 [citation:来源N](URL)；Claim/Evidence 只表达候选关系，不得声明人工 confirmed。
```

- [ ] **Step 4: 运行资格、Prompt 和工具回归**

Run:

```powershell
cd backend
$env:PYTHONPATH='.'
uv run pytest tests/test_evidence_profile_agent.py tests/test_lead_agent_prompt.py tests/test_tool_deduplication.py tests/test_deferred_tool_crosscontext.py -v
uv run ruff check packages/harness/deerflow/evaluation/evidence_profile.py packages/harness/deerflow/agents/lead_agent/agent.py tests/test_evidence_profile_agent.py
```

Expected: PASS；只有完整允许上下文包含 finalizer。

- [ ] **Step 5: 提交**

```powershell
git add backend/packages/harness/deerflow/evaluation/evidence_profile.py backend/packages/harness/deerflow/agents/lead_agent/agent.py backend/tests/test_evidence_profile_agent.py backend/tests/test_lead_agent_prompt.py
git commit -m "feat: gate evidence finalization by profile"
```

---

### Task 4: 增加事件持久化就绪检查

**Files:**
- Modify: `backend/app/gateway/deps.py`
- Modify: `backend/app/gateway/evidence_validation/service.py`
- Modify: `backend/app/gateway/evidence_validation/collector.py`
- Test: `backend/tests/test_evidence_validation_service.py`
- Test: `backend/tests/test_gateway_config_freshness.py`
- Test: `backend/tests/test_run_event_store.py`

**Interfaces:**
- `ShadowValidationService.__init__` 新增冻结的 `run_events_config`，与实际 store 同一启动快照。`detect_event_store_backend(event_store, run_events_config) -> Literal["memory", "db", "jsonl", "unknown"]` 必须优先识别实际 store，避免配置为 db 但 factory 回退 memory 时误报。
- `collect_shadow_payload(..., event_backend: str | None)` 在非 `db`/`jsonl` 时加入 `non_persistent_event_store`。
- Gateway 启动时 evidence validation enabled 且 event backend=`memory` 只记录警告，不阻断主服务。

- [ ] **Step 1: 写失败测试**

```python
def test_memory_backend_marks_non_persistent_gap():
    payload, state, _ = collect_shadow_payload(..., event_backend="memory")
    assert "non_persistent_event_store" in payload["audit"]["data_gaps"]


def test_db_backend_does_not_mark_non_persistent_gap():
    payload, _, _ = collect_shadow_payload(..., event_backend="db")
    assert "non_persistent_event_store" not in payload["audit"]["data_gaps"]
```

补充配置冻结测试：热重载不能让 service 误报与实际 store 不一致的 backend。

- [ ] **Step 2: 运行失败测试**

Run: `cd backend; $env:PYTHONPATH='.'; uv run pytest tests/test_evidence_validation_service.py tests/test_gateway_config_freshness.py tests/test_run_event_store.py -v`

Expected: 新断言 FAIL。

- [ ] **Step 3: 实现只告警、不破坏主流程的就绪检查**

`deps.py` 构建 store 后把同一 `run_events_config` 传给 service；日志只输出 backend/profile 数量，不输出账号列表。数据库 backend 不可用导致 factory 回退 memory 时，应以实际 store 类型为准并标记不持久化。

- [ ] **Step 4: 运行持久化、配置和所有者回归**

Run:

```powershell
cd backend
$env:PYTHONPATH='.'
uv run pytest tests/test_evidence_validation_service.py tests/test_gateway_config_freshness.py tests/test_run_event_store.py tests/test_owner_isolation.py tests/test_persistence_timezone.py -v
uv run ruff check app/gateway/deps.py app/gateway/evidence_validation packages/harness/deerflow/runtime/events tests/test_evidence_validation_service.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add backend/app/gateway/deps.py backend/app/gateway/evidence_validation/service.py backend/app/gateway/evidence_validation/collector.py backend/tests/test_evidence_validation_service.py backend/tests/test_gateway_config_freshness.py backend/tests/test_run_event_store.py
git commit -m "feat: report evidence event persistence readiness"
```

---

### Task 5: 从真实事件构建页面观察与结构化证据

**Files:**
- Create: `backend/app/gateway/evidence_validation/observations.py`
- Modify: `backend/app/gateway/evidence_validation/collector.py`
- Test: `backend/tests/test_evidence_validation_observations.py`
- Test: `backend/tests/test_evidence_validation_collector.py`

**Interfaces:**
- Produces: `collect_observations(events: list[dict]) -> ObservationIndex`，按 `tool_call_id` 关联 AI tool call 与 ToolMessage result。
- Produces: `select_evidence_submission(events: list[dict]) -> tuple[dict | None, list[str]]`。
- Produces: `apply_collection_status(submission, observations) -> claims/evidence/metrics/findings_input`。

- [ ] **Step 1: 写事件关联与异常失败测试**

覆盖：

- web_search 次数来自真实 tool result；
- web_fetch URL 来自 tool call args，正文来自配对 result；
- 跟踪参数和敏感参数脱敏后再匹配；
- `excerpt` 在完整正文中找到 -> `observed`；
- 完整正文找不到 -> `observed` + `excerpt_not_found`；
- `content_truncated=True` -> `truncated`，不得误判不存在；
- URL 没有真实访问 -> `unobserved`；
- malformed evidence event -> `malformed_evidence_report`；
- 多个提交事件 -> 使用与最终 AI `message_id` 匹配的最后一个，并加入 `duplicate_evidence_report_events`；
- message_id 无法匹配 -> `evidence_report_message_mismatch`；
- 可见 citation URL 与 `citation_evidence_ids` 不一致 -> 明确 finding input；
- 结构化载荷指标包含字符数、Claim/Evidence/引用数量、摘录字符分布和唯一来源数。

- [ ] **Step 2: 运行失败测试**

Run: `cd backend; $env:PYTHONPATH='.'; uv run pytest tests/test_evidence_validation_observations.py tests/test_evidence_validation_collector.py -v`

Expected: 新模块或断言 FAIL。

- [ ] **Step 3: 实现 ObservationIndex 和 collector v2**

只读取 `evidence.report.submitted`，不从自由文本猜 Claim/Evidence。对文本匹配只做空白规范化后的包含判断；不得引入相似度模型。新 submission 存在且格式有效时 `semantic_evaluation="evaluated"`；缺少、格式错误或 message 版本不一致时保持 `not_evaluable`。

新 live evidence 输出：

```python
{
    **candidate,
    "canonical_url": canonicalize_url(candidate["source_url"]),
    "accessed_at": observation.accessed_at,
    "collection_status": "observed",
    "review_status": "pending",
}
```

不得让 Agent 输入覆盖系统字段。

- [ ] **Step 4: 运行采集器与 B1 服务回归**

Run:

```powershell
cd backend
$env:PYTHONPATH='.'
uv run pytest tests/test_evidence_validation_observations.py tests/test_evidence_validation_collector.py tests/test_evidence_validation_service.py -v
uv run ruff check app/gateway/evidence_validation tests/test_evidence_validation_observations.py tests/test_evidence_validation_collector.py
```

Expected: PASS。

- [ ] **Step 5: 提交**

```powershell
git add backend/app/gateway/evidence_validation/observations.py backend/app/gateway/evidence_validation/collector.py backend/tests/test_evidence_validation_observations.py backend/tests/test_evidence_validation_collector.py
git commit -m "feat: collect persisted evidence observations"
```

---

### Task 6: 扩展确定性校验并完成零费用后端闭环

**Files:**
- Modify: `backend/packages/harness/deerflow/evaluation/evidence_validator.py`
- Modify: `backend/app/gateway/evidence_validation/service.py`
- Test: `backend/tests/test_evidence_evaluation_core.py`
- Test: `backend/tests/test_evidence_validation_service.py`
- Create: `backend/tests/test_evidence_validation_persisted_flow.py`

**Interfaces:**
- 新 live contract 读取 `collection_status` 与 `review_status`；旧固定夹具继续读取 legacy `status`。
- `unobserved`、关键 Claim 无 Evidence、citation 绑定不一致、完整页面中摘录不存在 -> blocker。
- `truncated`、无法自动判断语义、`review_status=pending` -> review_required，不假装 confirmed。

- [ ] **Step 1: 写新旧状态兼容失败测试**

```python
def test_observed_pending_source_reaches_human_review_not_confirmed():
    result = validate(make_live_payload(collection_status="observed", review_status="pending"))
    assert result["status"] == "review_required"


def test_unobserved_source_blocks():
    result = validate(make_live_payload(collection_status="unobserved", review_status="pending"))
    assert result["status"] == "blocked"
```

再断言：legacy B0 clean fixture 仍为原状态；8 个 B0 manifest 回放仍零不一致。

- [ ] **Step 2: 写 SQLite 持久化闭环失败测试**

测试用临时 SQLite：创建 `DbRunEventStore` -> 写 human/search/fetch/evidence/final events -> flush/释放第一个 store -> 新建第二个 store -> 运行 `ShadowValidationService.process_run()`。断言：

```python
assert record["semantic_evaluation"] == "evaluated"
assert record["auto_status"] in {"blocked", "review_required"}
assert record["run_id"] == run_id
assert run_after["status"] == "success"
assert run_after["llm_call_count"] == run_before["llm_call_count"]
```

加入跨 owner 查询为空、相同 report hash 幂等和事件缺失 `not_evaluable`。

- [ ] **Step 3: 实现 validator v2 兼容分支**

用显式 helper 读取：

```python
def _collection_status(item):
    return item.get("collection_status")


def _review_status(item):
    return item.get("review_status", item.get("status"))
```

存在 `collection_status` 时禁止回退到 Agent 提交的 legacy `status`；仅没有新字段的旧夹具使用 legacy 行为。自动状态永远不能由 `review_status=pending` 变成 confirmed。

- [ ] **Step 4: 运行专项、边界和 B0 回放**

Run:

```powershell
cd backend
$env:PYTHONPATH='.'
uv run pytest tests/test_evidence_evaluation_core.py tests/test_evidence_submission.py tests/test_submit_evidence_report_tool.py tests/test_evidence_profile_agent.py tests/test_evidence_validation_observations.py tests/test_evidence_validation_collector.py tests/test_evidence_validation_service.py tests/test_evidence_validation_persisted_flow.py tests/test_evidence_validation_repository.py tests/test_evidence_validation_api.py tests/test_evidence_validation_dispatcher.py -v
cd ..
python scripts/replay_evidence_validation.py tests/product/fixtures/b0_manifest.json
```

Expected: 专项全部 PASS；8 samples、false_releases=0、false_blocks=0、mismatches=0。

- [ ] **Step 5: 提交**

```powershell
git add backend/packages/harness/deerflow/evaluation/evidence_validator.py backend/app/gateway/evidence_validation/service.py backend/tests/test_evidence_evaluation_core.py backend/tests/test_evidence_validation_service.py backend/tests/test_evidence_validation_persisted_flow.py
git commit -m "feat: validate persisted evidence submissions"
```

---

### Task 7: 可点击引用、全量差分与本机零费用验收

**Files:**
- Modify: `frontend/tests/e2e/thread-history.spec.ts`
- Modify: `README.md`
- Modify: `backend/CLAUDE.md`
- Modify: `docs/product/STAGE_B_INTEGRATION_REVIEW.md`
- Create: `docs/product/evidence-validator-results/B1_1_ZERO_COST_ACCEPTANCE.md`
- Modify: `MEMORY.md`
- Local-only: `config.yaml`，将 `run_events.backend` 改为 `db`，不得提交。

**Interfaces:**
- Consumes: Tasks 1—6 的 finalizer、持久化事件、collector 和 validator。
- Produces: 单个真实付费样本之前的 Go/No-Go 结论；不包含真实模型调用。

- [ ] **Step 1: 增加引用浏览器测试**

在 mock thread 中加入：

```ts
content:
  "Deep Research 会执行研究。[citation:来源1](https://example.com/source)",
```

Playwright 断言：页面显示“来源1”；对应 `<a>` 的 `href` 正确，`target="_blank"`，`rel` 包含 `noopener` 和 `noreferrer`。不得真的访问 example.com。

Run: `cd frontend; pnpm test:e2e -- thread-history.spec.ts`

Expected: PASS。

- [ ] **Step 2: 核对执行前基线证据**

确认 Execution Preflight 已在本地 SDD ledger 记录 base commit、工作区状态和 backend 全量结果。若缺失，不得把当前失败主观归因为“原有问题”；先补充可验证的隔离重跑和历史 B1 验收对照。

- [ ] **Step 3: 运行最终静态、专项、产品和全量差分**

```powershell
cd backend
$env:PYTHONPATH='.'
uv run ruff check app/gateway/evidence_validation app/gateway/deps.py packages/harness/deerflow/evaluation packages/harness/deerflow/tools/builtins packages/harness/deerflow/runtime/journal.py tests/test_evidence_*.py tests/test_submit_evidence_report_tool.py
uv run pytest tests/test_evidence_evaluation_core.py tests/test_evidence_submission.py tests/test_submit_evidence_report_tool.py tests/test_evidence_profile_agent.py tests/test_evidence_validation_observations.py tests/test_evidence_validation_collector.py tests/test_evidence_validation_service.py tests/test_evidence_validation_persisted_flow.py tests/test_evidence_validation_repository.py tests/test_evidence_validation_api.py tests/test_evidence_validation_dispatcher.py tests/test_owner_isolation.py tests/test_gateway_run_drain_shutdown.py -v
uv run pytest tests/ -q
cd ..
python -m unittest discover -s tests/product -p 'test_*.py' -v
python scripts/replay_evidence_validation.py tests/product/fixtures/b0_manifest.json
python -m compileall -q backend/app/gateway/evidence_validation backend/packages/harness/deerflow/evaluation backend/packages/harness/deerflow/tools/builtins
cd frontend
pnpm test:e2e -- thread-history.spec.ts
pnpm typecheck
cd ..
git diff --check
```

Expected: 专项、产品、B0、引用 E2E、类型和静态检查全部通过；全量对比 fresh 基线没有 B1.1 相关新增失败。若全量有新增失败，隔离重跑并归因，未归因前不进入本机验收。

- [ ] **Step 4: 切换本机事件存储并做零费用运行验收**

先确认 Dify 运行容器仍为 0；只在 Git 忽略的 `config.yaml` 中把 `run_events.backend` 改为 `db`，重建/重启受影响 Gateway。不得发送 DeerFlow 消息。

验证：

- `/health` HTTP 200；
- OpenAPI 保留两个 evidence-validation 路径；
- 日志不再出现 non-persistent warning；
- 程序化插入的测试 run/event 经 Gateway/DbRunEventStore 重建后仍可读取；
- 结构化事件、最终 AI message 和 validation record 的 message_id/report_hash 一致；
- run status、Token 和 llm_call_count 未变化；
- Gateway 日志没有新增 `chat/completions`；
- `config.yaml` 未出现在 Git 状态；
- Dify 仍为 0。

程序化测试数据使用明显的 `b1-1-zero-cost-*` 标识，并在验收后通过所有者范围 API/仓储删除；删除前后均记录数量，不能碰真实 T001 数据。

- [ ] **Step 5: 更新文档和项目记忆**

验收报告必须记录：

- 这是程序化零费用 run，不是真实模型样本；
- 事件重启前后数量与 message_id；
- 结构化工具假模型调用数；
- citation 浏览器测试；
- B0 回放；
- Token 上限仍未设置；
- 仍需用户另行授权一个真实付费样本；
- 全量测试真实范围与任何基线失败。

README/CLAUDE 写清配置、profile gating、状态分层、默认关闭和回退行为。

- [ ] **Step 6: 安全检查并提交**

确认 diff/待提交文件中没有完整真实 user ID、密钥、带敏感 query 的 URL、`config.yaml` 或临时浏览器页面。

```powershell
git add frontend/tests/e2e/thread-history.spec.ts README.md backend/CLAUDE.md docs/product/STAGE_B_INTEGRATION_REVIEW.md docs/product/evidence-validator-results/B1_1_ZERO_COST_ACCEPTANCE.md MEMORY.md
git diff --cached --check
git commit -m "docs: record b1.1 zero-cost acceptance"
```

- [ ] **Step 7: 停在真实费用门前**

输出 B1.1 已实现内容、真实验证范围、未验证项和 AI 产品经理学习结论。不得自动发送研究任务；下一步必须由用户单独确认“一个真实付费样本”的任务、模型、范围和费用边界。
