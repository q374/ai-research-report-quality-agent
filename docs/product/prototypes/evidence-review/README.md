# 证据复核界面 B0 静态原型

入口：`index.html`

## 用途

展示四种质量状态及人工复核信息架构：

- 不可发布
- 待人工复核
- 已确认
- 校验异常

页面数据来自本地固定夹具，只做界面与交互验证：

- 不连接 DeerFlow API。
- 不保存人工决定。
- 不调用模型或网络服务。
- 不代表功能已经接入或上线。

## 生成方式

```powershell
python scripts/render_evidence_review_prototype.py --output docs/product/prototypes/evidence-review/index.html
```

## 验收重点

1. `blocked` 和 `validator_error` 不能点击“确认通过”。
2. `review_required` 可以进入人工确认。
3. `confirmed` 展示复核人和时间。
4. 页面同时展示报告陈述、证据原文、校验发现和人工动作。
5. 窄屏下四个区域改为单列，不产生横向溢出。
