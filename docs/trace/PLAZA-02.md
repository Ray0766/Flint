# PLAZA-02 · 广场②：地区与源筛选上屏

> v0.4.1 第 5 批第五张。依赖 `PLAZA-01`（verified）。
> **状态：started，尚未写任何代码。** 上一轮在卡边界收敛（`worker.md §2.5`：
> 上下文接近上限时收敛到卡边界，NEVER 在卡中途弃档）。下面是开工前**已经实测过**的东西，
> 下一轮直接用，NEVER 重新推一遍。

## 一、已实测的端点实况（本机真栈 :8000，2026-08-08）

```
GET /settings/locale
{"lang":"zh","region":"CN",
 "options":{"lang":["en","zh"],
            "region":["AU","CN","FR","GB","IT","JP","KR","SG","US"]}}      ← 九区在这里，NEVER 在广场再抄一份

GET /plaza/hot?day=2026-07-04&region=CN   → 200                            ← region 参数真的通
```

## 二、两个组件的现成签名（已读，NEVER 另写）

- `web/components/region-switch/RegionSwitch.tsx`
  `{ region, regions: readonly string[] | null, lang, onChange({region, lang}) }`
  - `regions === null || []` → 自带「接口未提供」姿态（`data-screen-state="not_provided"`）；
  - `onChange` 里 **lang 原样带回**——切区 NEVER 改语言（PRINCIPLES#A3）。
- `web/components/source-columns/SourceColumns.tsx`
  `{ statements: { sourceId, region, text }[] }`
  - 按 **region** 分列，`region === ""` 归到 `UNKNOWN_REGION_KEY` 且**恒排最后**；
  - `statements` 为空 → `source-columns-empty`。

## 三、开工时要先想清楚的一件事（下一轮的第一个决定）

卡面 acceptance 写着「`by_source` 分列 **≥2 列**且无合成句」，而 `SourceColumns`
**是按 region 分列的**，`PlazaCluster.by_source` 里**没有每个源的地区**
（实测形如 `{"weibo":100}`、`{"ghtrend":0,"trends":100}`）。

两条路，二选一**必须在 trace 写明理由**：

1. **每个源一列**（`region` 位填源自己的键）——那样「≥2 列」在多源簇上自然成立，
   但会把 `SourceColumns` 的 region 语义借去表示别的东西，**与 `DS-02` 那次「NEVER 借一个
   已经有主的记号说另一件事」是同一类风险**；
2. **保持 region 语义**，源的地区从 `GET /settings/locale` 或源注册表拿——
   若拿不到，那就是一个真缺口，按 `docs/blocked/` 上报，屏上按未归区单列呈现，
   **NEVER 编一个地区**。

先去核 `HOTSPOT-07` 既有判据（`docs/trace/HOTSPOT-01.md` 与
`web/components/source-columns/*.test.tsx`）当时是怎么定义「列」的——
**它已经有口径，照它做，NEVER 自己重定一个。**

## 四、本轮已就绪的上下文（不必重读）

- 广场屏现在接的是 `web/components/plaza/PlazaCards.tsx`（堆叠 + 网格），
  取数仍在 `web/app/plaza/page.tsx` 的 `useEffect` 里（`fetchPlazaHot(day)`）；
- 卡面是 `HotspotCard`，七槽，广场上只有 `nameNative` 与 `heat` 有值，其余逐槽隐藏；
- 广场屏已退出 34em 阅读宽度（`.screen:has(.plaza)`），1440px 下网格 3 列。
