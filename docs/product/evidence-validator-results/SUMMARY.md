# 证据校验器阶段 A 离线原型结果

更新时间：2026-09-19
验证范围：T001 v1、v2、v3 三份既有合成输出
运行方式：本地确定性规则；不联网、不调用模型、不修改 DeerFlow 生成链

## 1. 验收结论

| 样本 | 系统字符数 | 页面查看 / 规范化唯一页 | 阻断规则 | 警告规则 | 发布状态 |
|---|---:|---:|---|---|---|
| T001 v1 | 1217 | 3 / 2 | EV-01、EV-03、EV-04、EV-06 | EV-07 | `blocked` |
| T001 v2 | 575 | 3 / 3 | EV-04、EV-08 | 无 | `blocked` |
| T001 v3 | 877 | 4 / 2 | EV-03、EV-06 | EV-06、EV-07 | `blocked` |

三份已知 Badcase 均未被错误放行。v3 的模型自报 560 字符未被采用，校验器按最终展示正文计算为 877 字符。

## 2. 已实现能力

- 对当前事实检查历史或过期证据依赖。
- 检查关键结论与 EvidenceItem 的绑定关系和可见引用。
- 对“未披露、未找到、未知”等否定性结论反查已绑定证据摘录。
- 检查 ResearchBrief 声明的必填维度。
- 由系统计算字符数、搜索次数、页面查看数和禁用工具。
- 去除 URL 锚点及跟踪参数，并用声明的 canonical URL 合并别名。
- 拦截待复核问题中没有证据的暂停、取消、涨价、下线等事实前提。
- 最小输入契约不完整时 fail-closed。
- 自动规则无阻断时仍进入 `review_required`；只有人工批准后才是 `confirmed`。

## 3. 验证证据

- 预期失败基线：实现文件不存在时，测试因 `FileNotFoundError` 失败。
- 实现后：7 项本地单元测试全部通过。
- 覆盖场景：三版已知 Badcase、真实可见字符计数、v3 重复 URL 归一、输入契约缺失、问题可操作性、人工批准闸门。
- 结构化结果：本目录下 `t001_v1.result.json`、`t001_v2.result.json`、`t001_v3.result.json`。

复现命令：

```powershell
python -m unittest discover -s tests/product -p "test_*.py" -v
python scripts/evidence_validator.py tests/product/fixtures/t001_v3.json
```

## 4. 真实性边界

- 这只是三份已知合成样本的离线回归，不是未知样本准确率、误报率或生产效果。
- Claim、EvidenceItem 和页面摘录由固定夹具提供；原型尚未从 DeerFlow 运行结果自动采集这些对象。
- 未验证重定向网络解析、页面内容漂移、复杂语义支持关系或真实用户效率提升。
- 本阶段新增模型调用 0 次，新增 API 费用 0 元。
- 尚未接入 DeerFlow 前后端，不能把原型称为已上线功能。

## 5. 下一阶段产品决策

阶段 B 接入评审已完成，结论为有条件进入 B0：先建立 ValidationRecord、ReviewDecision、report_hash、固定样本回放和静态复核界面，不直接对真实回答启用硬门禁。完整决策见 `docs/product/STAGE_B_INTEGRATION_REVIEW.md`。仍不运行 T002 或新的付费样本。

## 6. 30 分钟讲解与验收

1. 5 分钟：用 T001 v1—v3 说明提示词自检为什么不可靠。
2. 5 分钟：解释 Brief、Claim、Evidence 和 Finding 四类产品对象。
3. 8 分钟：演示 v3 如何被 EV-03、EV-06、EV-07 定位。
4. 5 分钟：演示无阻断报告为什么仍需人工批准。
5. 4 分钟：说明零模型成本、fail-closed 与不自动改写的取舍。
6. 3 分钟：说明合成样本边界和阶段 B 接入决策。

## 7. B0 补充结果

阶段 A 之后已完成 B0：新增 5 份正向/边界夹具，与 T001 v1 至 v3 合计回放 8 份；固定样本内错误放行 0、错误阻断 0。可执行契约覆盖 report_hash、权限、人工决定、幂等和异常 fail-closed；静态界面展示四种状态。

完整结果见 `B0_REPLAY_SUMMARY.md`。B0 仍未接入 DeerFlow 真实运行事件或数据库，刷新后的决定持久化、未知样本准确率和真实用户效果均未验证。
