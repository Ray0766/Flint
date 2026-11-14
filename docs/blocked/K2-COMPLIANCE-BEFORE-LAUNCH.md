# K2-COMPLIANCE-BEFORE-LAUNCH · 上线（商用）前必须补的抓取手续

**状态** open

> **逐源清单已搬到 `docs/上线前合规手续清单.md`（COMP-01，owner 2026-08-04 裁决：
> 手续单独立档）。那份是唯一入口。**
> 本单只留「这是一张有到期日的欠条」这件事本身与切档办法；
> 逐源的实测态 / 派生态 / 手续 / 判据**只在那份里有一份**——
> 这里原本自带的那张表已删掉：`assets/source_legal_status.yaml` 会随重测变，
> 手抄的表不会，两份迟早各说各的，而读的人分不出哪份是真的。

**立卡** worker / K2-01 · 2026-08-04
**触发条件** 本产品从非商业转为**商用上线**的那一刻
**危害** 高 —— 不补就上线 = 在明知 `Disallow` 的情况下商用抓取
**这不是缺陷，是一张有到期日的欠条**

## 现状：owner 已裁决「记录但不阻断」

owner 2026-08-04 裁决：**非商业用途下先取数**，合规状态照实记录并带到产物，
但不拿它拦抓取。裁决落成机读记录：`flint/region/legal_policy.py#RECORD_ONLY`。

裁决的**范围写死在记录里**（`scope="non_commercial"`）。范围变了，裁决就不再覆盖。

## 实测结果

**逐源那张表在 `docs/上线前合规手续清单.md`**，由
`assets/source_legal_status.yaml` 生成、有判据逐字守着。这里不再复制一份。

要点两句（不含逐源数据，因此漂不起来）：

- 一部分源实测为 disallowed，派生 restricted。上线前每一条都要有结论，
  不能靠现行裁决兜着——三选一（签约取数 / 换源 / 走 E6 缺数据行）写在清单里；
- `tos_url` **只记地址不记结论**。robots.txt 是机器可判的，**服务条款是人读的**——
  机器判不了的东西 NEVER 由机器给个结论顶上。ToS 的人读结论属 owner/法务面，
  逐条的手续与判据在清单里。

## 怎么恢复阻断（一步）

`flint/region/legal_policy.py` 里把

```python
OWNER_DECISION: Final[LegalDecision] = RECORD_ONLY
```

改成

```python
OWNER_DECISION: Final[LegalDecision] = BLOCK
```

改完立刻回到 REGION-07 的原行为：只放行 `allowed`，其余落降级行 + 抛 `FetchDenied`。
`flint/region/fetch_gate.py` **本身一个字没改过**——门一直在，只是这一层没让它拦人。
`tests/v041/test_legal_status_recorded.py#test_flipping_the_switch_back_blocks_again`
恒在跑这条路径，所以它 NEVER 会悄悄烂掉。

## owner 上线前要给的三样

1. **八条 ToS 的人读结论**（尤其 `weibo` / `arxiv` / `reddit_data_api` 三条）；
2. **三个 `restricted` 源的处置**：签约取数 / 换源 / 该区走 E6 缺数据行，三选一；
3. **切档确认**：商用上线时把 `OWNER_DECISION` 切到 `BLOCK`，
   并把届时确认合规的源在种子表里填成 `allowed`。
