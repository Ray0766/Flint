# NAV-05 · 主链路串成一条真能走的路

**结论**：可达 12 → **15**，孤岛 9 → **6**。后半段通了；前半段**走不通**，
两条缺口逐条开单（`docs/blocked/MAIN-CHAIN-HAS-NO-LIVE-ENTRANCE.md`）。

装载：卡 `NAV-05` · `web/app/**` · `assets/screen_graph.json` ·
`docs/前端功能说明-v2.md` · `docs/屏对照表-v041.md`

---

## 1 接上的九条边

| 从 | 到 | 怎么进 |
|---|---|---|
| 主题列表 | 主题详情 | 每条主题的「查看这条主题」（带 `?project=`） |
| 主题列表 | 项目总览 / 发起分析 | 屏底两条 |
| 主题详情 | 发起分析 | 「用这条主题发起分析」（要 `?project=`） |
| 项目总览 | 主题列表 / 发起分析 / 计划书受众 | 三条支路 |
| Job 进度 | Gate① 判定 | **跑完了才给** |
| 报告 | 质量卡 / vibe_pack / 干预记录 | 三个同族屏 |

### 选中与查看是两件事

主题卡上原本只有一个「选为本项目的主题」（POST 落盘）。加的是**另一个**入口。
合成一个的话，用户想看一眼就会顺手把项目的主题改掉——与 `DEC-042` ① 同一条。

### Job → Gate 为什么只在 `done` 之后给

作业还在跑时点过去，判定屏会如实说「未判定」。那句话没错，
**可它读起来像「这次没判出结果」，而真相是「还没跑到」**。
失败那一路也不给：失败的作业不会有判定。

### 受众分叉从项目总览进，不从报告屏

报告屏只有交付物 id，而 `GET /deliverables/{id}/blocks` 回的是
`{deliverable_id, blocks}`——**交付物 → 项目没有可读的对应关系**。
从那边接就得猜一个项目 id。项目总览手上正好有。

### 三处入口都放在取数状态**外面**

取数失败 NEVER 把出路一起带走：这一屏读没读到，与「还能去哪」没有关系。

## 2 项目 id 一路带着走（`?project=`）

主题详情**不知道**自己属于哪个项目——`GET /topics/{id}` 回的 `Topic` 里
没有 `project_id`（冻结件里也没有）。而下一跳「发起分析」是按项目发起的。

所以由**调用方**带过来，与 `DEC-012` / `AnalysisView` 的 `verdictJobId` 同一形态。
没带就在屏上如实说，`NEVER 拿 topic_id 拼一个项目去试`：
猜错时用户会把这条主题的分析发起到**别人的项目**上，**而那要花钱**。

`undefined`（还没读 URL）与 `null`（读过了、没给）分开，否则会先闪一句假话再改口。

## 3 走不通的那两跳：逐条列名，NEVER 假链接

```
可达性：23 屏 · 入口 6 个 · 走得到 15 屏 · 豁免 1 屏
孤岛 6 屏：/combo · /projects/[id] · …/analysis · …/proposal · …/topics · /topics/[id]
```

这六屏**彼此之间已经连通**（本卡接的），缺的是走进这一族的**第一步**：

1. **`POST /workbenches` 没挂** → 入台永远拿不到 `ok` → 工作台进不去；
   即便进去了，`GET /workbenches` 未建，工作台不知道自己属于哪个项目。
2. **广场没有「多选卡片建组合」** → `/combo` 没有入口。那是一个功能，不是一条链接。

单据里写了三种顶法各自会说出的假话：

| 顶法 | 假话 |
|---|---|
| 顶栏加一项「项目」 | 项目 id 从哪来？拼一个 → 落进别人的项目或 404 |
| 广场卡片链到 `/projects/{cluster_id}/topics` | cluster ≠ project，这条对应关系不存在 |
| `/combo` 进顶栏 | 点进去是一屏说明文字，不是一个去处 |

## 4 acceptance ⑤：尺子没转绿，而每一座孤岛都有主

卡上写的是「**MUST 转绿：22 屏全部可达，或不可达的逐条在图里标明理由**」。
交付的是后半句：六座孤岛各自带 `island_reason` + `island_sheet`，
指向一张**开着的**单。判据 `test_every_island_has_a_reason_and_an_open_sheet` 逐条查，
并在最后断言 `check().clean is False`——

> **写理由不顶红。** 尺子照样报这六座；写理由只是让「没人管」与
> 「有主，等一件具体的东西」分得开。

这与 `exempt` 的纪律是一致的：`NEVER 把「还没接线」写进去顶掉红`。

## 5 判据：真走一遍，15 跳，id 全从上一屏取

`tests/v041/test_main_chain_walk.py` 用 playwright 走完整 15 跳，逐跳断言
**200 + 渲染出这一跳该有的东西**。

`NEVER 只断言 href 存在`——href 在不代表点得过去：目标屏可能 404、
可能拿着错 id 恒空、可能渲染的是「接口未提供」。
`NEVER 硬编一串 id`——那是同一个病的另一种形态：上一屏不给这个 id 了判据也不知道。

唯一一处外部给的 id 是 `SEED_PROJECT`（项目族没有活的入口，那一段直接进屏），
它从 demo 库里查出来，且判据名里写明「[直接进屏]」。

实测（`.ui-probe/nav05_walk.json`）：15/15 rendered，控制台 0 error，
Gate① 那一跳拿到的是**真判定**（`got: "verdict"`）。

## 6 三个断点

**① 两个样例 job 混成了一个。** `job-gate1-live-qwen` 是 demo 库里唯一有判定的作业，
而它**不属于探针那个用户**——Job 屏对它回「无权查看」。
拿它去看 Job 屏，红的是样例给错了，不是屏坏了（`fe_smoke.py` 的样例登记里
为同一件事写过一段）。改后：Job 屏用 `probe-owned-ingest`，判定屏用前者。

**② 阴性对照的前提过期了。** `test_removing_one_link_turns_a_screen_into_an_island`
原本摘 `/plaza → /gate/[id]` 断言整条链掉下来。本卡给 Job 屏接上判定入口之后，
判定屏**有了第二条路**，摘一条不再让它掉下来。
改后摘 `/gate → /deliverables`：报告那一族只有这一条路进去，级联仍然量得到，
而判定屏因为有第二条路照样可达——**比改前判得更细**。

**③ `test_ui11` 判「源码里不许出现 `/topics`」。** 本卡给项目总览加了三条**链接**，
子串出现，判据当场红。它拦下的不是「又拼了三个请求」，是「屏上多了一条链接」。

同一形状第十四次。改后判它真正要挡的那件事：**只有一个 `useScreenData<` 调用点**，
且取的是那条一次查齐的端点；三个子串仍然只许出现在 `href=` 里。
（数调用点而不是数标识符出现次数——import 那一行自己就带两处。）

## 7 门

```
pytest tests/v041/test_main_chain_walk.py -q   14 passed（15 跳真走）
pytest tests/v041/ -q                          2883 passed
vitest run                                     84 files · 850 passed
tsc --noEmit                                   0
ruff check .                                   All checks passed
fe_smoke（23 屏 × 明暗）                        92 行「无溢出」
check_reachability                             EXIT=1 · 可达 15 · 孤岛 6（各有主）· 走不通 1 · 豁免 1
```

改过的既有判据两条（阴性对照 · `test_ui11`），改因都写在它们自己的注释里。
落盘产物重生成：对账表 · gauge_map · fe_smoke.json。
