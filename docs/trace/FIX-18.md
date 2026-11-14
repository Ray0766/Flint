# FIX-18 · 热点分析屏缺来源分列（`NAV-02` 的 acceptance③④）

**结论**：承载屏里把 `<AnalysisView/>` 与来源分列**并排渲染**，
**封版件一个字没动**。真栈实测屏上出现「各源怎么说 | CN | 微博热搜：热搜话题02」。
`verify_cmd` 15 条全绿（含 5 条真浏览器）；`ruff` / `tsc 0` / `vitest 857` /
邻近四把尺子 79 条全绿。

装载：`docs/steward/tasks-v041-b9.json#FIX-18` · `docs/trace/NAV-02.md` ·
`web/app/clusters/[id]/page.tsx` · `web/views/analysis/AnalysisView.tsx`（**只读**）·
`web/components/plaza/ClusterSourceLines.tsx` · `web/components/source-columns/` ·
`web/lib/viewsClient.ts` · `flint/api/views.py`（`by_source_text` 出处）
（实测装载 ≈ 27k tokens，预算 40k）

---

## 1 欠的那一样，与**为什么不动封版件**

`NAV-02` 卡面 ③④ 要求解析界面有三样：判定 · 证据概览 · **来源分列**。
前两样在 `AnalysisView` 里；第三样实查 `page.tsx` 与 `AnalysisView` 里
`SourceColumns` / `ClusterSourceLines` **均 0 处**。

`AnalysisView` 是 **v0.4 封版件**。`FIX-19` 拿到的许可**只限加类名与样式**——
改它的取数路径**不在那条许可里**（`worker.md` §9.2 / `DEC-021`）。

卡面自己写了修法：**承载屏里并排渲染**。本卡照做，
并从**封版件那一侧**留了一条判据（`test_the_sealed_analysis_view_was_not_touched`）：
它里面仍然没有来源分列的任何痕迹——也就是说本卡没有绕过许可去动它。

## 2 各源原话是**当天**的事实，所以要一个日期

`by_source_text` 只在 `GET /plaza/hot?day=…` 的簇行上（`flint/api/views.py`）——
它记的是**那一天**各源怎么说的。而 `/clusters/[id]` 手上只有一个 `clusterId`。

所以这一块按 `?day=` 取，URL 上没带时用与广场同一个默认值。
**这不是将就**：一个不带日期的「原话」说不清是哪天说的。

**为什么不加一条按簇取词面的端点**：那要动 `flint/api/views.py`，
而本卡 outputs 只有 `web/app/clusters/` 与判据文件——
本批 rules 写死「改动面大于卡上 outputs → 停下走 `docs/blocked/`」。
按天取在 outputs 之内，且语义上站得住，所以不必停。

## 3 四态各自成一态

| 态 | 记号 | 什么意思 | 用户该做什么 |
|---|---|---|---|
| 还在取 | `loading` | 还没查 | 等 |
| 查到了 | `ready` | 这一天的榜里有它 | — |
| 这一天没有它 | `not_on_this_day` | **查过了，它不在这一天** | 换一天 |
| 读失败 | `failed` | 没查成 | 重试 |

第三态与第四态**尤其不能合并**：合成一句「读失败」的话，用户会去重试，
而重试一百次也不会有结果。两者在「屏上没有分列」这个结果上长得一模一样。

「这一天没有它」那句话**点名是哪一天**——不说的话，用户不知道该换哪个。

## 4 复用，而不是另写一份

`ClusterSourceLines`（`REGION-12` 建的那一层）已经做完三件事：
三张并行表配对成 `SourceColumns` 的三元组、`global` 归未归区那一列、
**缺词面的源另起一行如实说「原话没查到」**。

另写一份的后果：① 广场与这一屏对同一条簇的原话会各自漂移；
② `FIX-17` 给它加的**可见署名**要再加一遍——而漏加的那一处，屏上分不出谁说的。

本屏**只搬运**：三张表原样交出去，一个字都不在这里加工
（判据只扫那三个入参，见 §6②）。

## 5 改前 / 改后 / 为什么非改不可

| 文件 | 改前 | 改后 | 为什么 |
|---|---|---|---|
| `web/app/clusters/[id]/sourceLines.tsx` | 不存在 | 新增：按天取簇行 → 交给 `ClusterSourceLines`，四态 | 承载屏那一半 |
| `web/app/clusters/[id]/page.tsx` | 只渲染 `<AnalysisView/>` | 与 `<ClusterSourceLinesForDay/>` **并排** | acceptance②；`AnalysisView` 那几行一个字没动 |
| `web/messages/{zh,en}.json` | — | 各 +3 条 | 四态里的三句话要有词条 |
| `tests/v041/test_analysis_entry_screens.py` | 钉字面量 `if (!found) return;` | 改判**守卫本身** | 见 §7 |

**`web/views/analysis/AnalysisView.tsx` 一个字节都没动。**

## 6 三处「红的是尺子自己」——都在本卡自己的判据里

① **占位串那条扫得太宽**：把 `data-source-lines-day={day ?? ""}` 也算成了占位串，
而那是**日期属性**的缺省值，与原话槽毫无关系。
改成只扫交给分列的那三个入参。**尺子扫得太宽时报的是一句读起来像真的的假话。**

② **切片切到了注释**：文件头写着「把 `<AnalysisView/>` 与 `<ClusterSourceLines/>`
并排渲染」，按第一处 `<ClusterSourceLines` 切会切到那句解释后面的 `/>`，
props 段是空的——于是判据报「三张表不是原样搬运」，**而它其实一个字都没读到**。
本轮第三次撞上「尺子读了注释」这个形状。

③ **锚点落在 import 行上**（§7 那条）：`fetchEvidenceCards` 第一次出现在 import 行，
按它切会把整个 effect 切掉。改锚 `Promise.all(`。

## 7 抓到一条**`ENTRY-04` 引起的**回归

```
tests/v041/test_analysis_entry_screens.py::test_no_cluster_id_means_no_request
  AssertionError: 没带簇 id 时仍然发了请求
```

`ENTRY-04` 让 `/combo` 接多簇之后，守卫从 `if (!found) return;` 变成了
`if (wanted.length === 0) return;`——**守卫还在，是那句字面量过期了**。

**这条是我上一张卡引起的，而上一张卡收尾时只跑了三把广场尺子，没跑到它。**
改判**这条纪律本身**：取数之前有一个提前 return，且它判的是「一个簇都没带」。
钉字面量的话，下一次改写法还要再来一趟，而每来一趟都要重新判断「这次红是真的吗」。

## 8 真栈实测

```
/clusters/c-20260704-000?day=2026-07-04
  state=ready  day=2026-07-04  analysis-view=1（判定那一半还在，是并排不是替换）
  屏上可见文本：各源怎么说 | CN | 微博热搜：热搜话题02
  source_ids=['weibo']（署名在屏上，FIX-17 的可见署名一并生效）
  console_errors=[]
```

图：`.ui-probe/fix18-cluster.png`

（词面 `热搜话题02` 是录制夹具的合成词——`CN-01` 得到 owner 点头之后
它会变成真实热点，**而本卡与那件事互不影响**：一个管「有没有分列」，
一个管「分列里写的是什么」。）

## 9 自审（`self_review=true`）

**① 判据覆盖 acceptance**：①三样齐（源码 + 真浏览器）；②不动封版件
（**从封版件那一侧量**）；③复用既有件 + `FIX-17` 署名一并生效（真浏览器量 `source_ids`）；
④原文非译文、缺词面 NEVER 塞占位串（源码只扫三个入参 + 真浏览器扫屏上没有占位串）；
⑤取渲染后的可见文本并打真栈。

**先红后绿**：判据先写，实现前 15 条全红。

**② 无冻结件偏离**：不碰后端，四件一字未动。
**③ 无禁用词**：0 命中。
**④ 复用断言在位**：`ClusterSourceLines` / `SourceColumns` / `fetchPlazaHot` 全部复用，
一个字没改；判据 `test_the_reused_layer_is_the_existing_one` 就是那条复用断言。
**⑤ 装载未超预算**：≈27k / 40k。

## 10 门

```
pytest tests/v041/test_analysis_source_columns.py -q   15 passed（含 5 条真浏览器）
ruff check . --no-cache                                All checks passed!
npx tsc --noEmit                                       0
npm test -- --run                                      85 档 857 passed
邻近四把尺子（analysis_entry_screens / source_columns_attribution /
  source_columns_verbatim / plaza_multiselect_combo）        79 passed
```

## 11 留给下游

1. **`FIX-19`（给 `AnalysisView` 加类名）**：本卡把分列**放在它外面**，
   所以 `FIX-19` 的边界一点没被本卡挤占——那张卡照旧只加类名与样式。
2. **按簇取词面的端点**：今天按天取（§2）。哪天有一张 outputs 含 `flint/api/` 的卡，
   可以考虑加一条按簇的读法，那时这一屏就不必带 `?day=` 了。
3. **`?day=` 从哪来**：广场跳过来时今天**不带**它（`web/app/plaza/` 不在本卡 outputs），
   于是落在默认那一天。带上会更准——留给某张 outputs 含 `web/app/plaza/` 的卡顺手做。
