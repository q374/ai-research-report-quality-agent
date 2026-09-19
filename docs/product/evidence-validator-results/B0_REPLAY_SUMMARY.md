# B0 证据校验离线回放结果

更新时间：2026-09-19

## 1. 回放范围

- 已知负样本：T001 v1、v2、v3，共 3 份。
- 新增正向/边界样本：5 份。
- 总计：8 份。
- 数据来源：本地固定夹具。
- 模型调用：0 次。
- 新增 API 费用：0 元。

## 2. 结果

| 类型 | 数量 | 自动状态 | 错误判断 |
|---|---:|---|---:|
| 已知负样本 | 3 | 全部 `blocked` | 错误放行 0 |
| 正向/边界样本 | 5 | 全部 `review_required` | 错误阻断 0 |
| 合计 | 8 | 与清单期望一致 | 不一致 0 |

正向/边界样本覆盖：

1. 当前事实由当前来源支持。
2. 历史事实明确按历史状态表达。
3. 正文恰好 800 字符，不应因边界值误阻断。
4. 两次访问同一页面的不同锚点，保留 2 次查看并合并为 1 个唯一来源。
5. 待人工复核项使用中性问题，不预设暂停、涨价或下线等事件。

所有正向样本的结构化 Claim 均能在最终展示正文中逐字定位，避免用“正文之外的隐藏 Claim”伪造覆盖完整性。

## 3. 可复现证据

- 清单：`tests/product/fixtures/b0_manifest.json`
- 结构化结果：`docs/product/evidence-validator-results/b0-replay.json`
- 回放器：`scripts/replay_evidence_validation.py`
- 测试：`tests/product/test_evidence_validation_replay.py`

运行命令：

```powershell
python -m unittest tests.product.test_evidence_validation_replay -v
python scripts/replay_evidence_validation.py tests/product/fixtures/b0_manifest.json --output docs/product/evidence-validator-results/b0-replay.json
```

## 4. 真实性边界

- “错误放行 0、错误阻断 0”只适用于这 8 份人工标注的固定样本。
- 5 份正向/边界样本是合成夹具，不是真实用户报告。
- 回放没有证明未知样本准确率、真实用户复核效率或生产稳定性。
- 当前仍未从 DeerFlow 的真实运行事件自动形成 Claim 与 Evidence。
