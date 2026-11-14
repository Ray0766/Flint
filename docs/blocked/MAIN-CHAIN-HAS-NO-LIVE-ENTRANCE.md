# 主链路中段没有活的入口：项目族六屏内部连通，而从产品面走不进去

**状态** closed · 2026-08-09 · `ENTRY-05`（开单人是 `NAV-05`；入口由 `ENTRY-04` 建出来、`ENTRY-05` 声明进图）

> 前端**已经接完**。这一单挡着的是两件后端/功能上的缺，`NEVER 用一条假链接把路连起来`。

## 现象

`NAV-05` 把主链路逐段接通之后，`tools/check_reachability.py` 报：

```
可达性：23 屏 · 入口 6 个 · 走得到 15 屏 · 豁免 1 屏

**孤岛 6 屏**（从入口出发走不到，且没有豁免理由）：
  ✗ /combo
  ✗ /projects/[id]
  ✗ /projects/[id]/analysis
  ✗ /projects/[id]/proposal
  ✗ /projects/[id]/topics
  ✗ /topics/[id]
```

这六屏**彼此之间已经连通**（本卡接的）：

```
/projects/[id]/topics ──┬──> /topics/[id] ──> /projects/[id]/analysis ──> /jobs/[id]
                        ├──> /projects/[id] ──┬──> /projects/[id]/topics
                        └──> /projects/[id]/analysis
                                              ├──> /projects/[id]/analysis
                                              └──> /projects/[id]/proposal
/combo ──> /projects/[id]/topics
```

**缺的是走进这一族的那第一步。**

## 两条进得来的路，各自缺什么

### ① 广场 →（入台）→ 图谱工作台 → 项目族

`POST /workbenches` **没挂**（实测框架 404，没有 `code`）。`NAV-03` 已把
「入台成功 → 跳工作台」接上，而入台永远拿不到 `ok`，所以那条边今天走不通
（图上标着 `blocked`，尺子把它单列在第三格）。

即便进了工作台也还差一步：`GET /workbenches` 未建，工作台屏**一个请求都不发**，
它不知道自己属于哪个项目，链不到主题列表。

**要什么**：`POST /workbenches`（回 `graph_id`）+ `GET /workbenches/{graph_id}`
（至少回它的 `project_id`）。

### ② 广场 →（多选卡片建组合）→ `/combo` → 主题列表

`/combo` 屏自己是好的：它按 `?cluster=` 取证据卡，没带就说清该怎么来
（`CHAIN-04` 的判据盯着「一张卡都不编」）。

缺的是**广场上的多选**：今天广场的卡片主体是导航（`DEC-042` ①），
三个按钮是收藏 / 入台 / 分享，**没有「选几张一起建组合」这个能力**。

`NAV-04` 当时的判断原样留着：给 `/combo` 硬塞一个顶栏入口的话，
用户点进去会落在一屏说明文字——**那不是入口，是一句「你怎么走到这儿的」**。

**要什么**：广场多选 + 「用选中的卡建组合」，带着 cluster id 进 `/combo`。

## 为什么不先接一条链接顶上

三种顶法都试过（在脑子里），三种都会说谎：

| 顶法 | 它说出的假话 |
|---|---|
| 顶栏加一项「项目」 | 项目 id 从哪来？拼一个 → 用户落进别人的项目或一个 404 |
| 广场卡片链到 `/projects/{cluster_id}/topics` | cluster ≠ project，这条对应关系不存在 |
| `/combo` 进顶栏 | 点进去是一屏说明文字，不是一个去处 |

`NAV-05` 的 acceptance ④ 原话：**走不通的那几跳逐条列名开单，
NEVER 用一条假链接把路连起来。**

## 现在能走到哪

```
顶栏 ─┬─ /plaza ──┬──> /clusters/[id]（热点分析，NAV-02）
      │           ├──> /gate/[id] ──> /deliverables/[id] ─┬─> …/export
      │           │                                       ├─> …/quality
      │           │                                       ├─> …/pack
      │           │                                       └─> …/interventions
      │           └──(入台，走不通)─> /workbenches/[id]
      ├─ /account ──> /billing
      ├─ /favorites · /design · /settings/locale
      └─ /demo ──> /jobs/[id] ──(done)──> /gate/[id]
```

报告那一段（Gate① → 报告 → 导出/质量卡/vibe_pack/干预）**本卡之后是通的**，
前提是手上有一个 job id——`/demo` 串屏能给出一个。

## 关掉这一单的条件

① 与 ② **任一**做完，且 `tools/check_reachability.py` 的孤岛名单里
不再有 `/projects/*` 与 `/topics/[id]`。到那天回来改
`tests/v041/test_main_chain_walk.py` 与 `test_reachability.py` 的基线。

---

## 关闭（`ENTRY-04` / `ENTRY-05`）

这张单要的是「走进项目那一族的第一步」。`ENTRY-04` 把它**建出来了**：广场卡片可多选，选够之后那条组合栏带着 `?clusters=` 跳 `/combo`。

`ENTRY-05` 把那条边两个方向都声明进 `assets/screen_graph.json`，于是 `/combo -> /projects/[id]/topics -> /projects/[id] -> analysis/proposal` 与 `/topics/[id]` **整条链跟着通**——那五屏自己一行都没改。

实测：**孤岛 6 → 0**，且豁免名单仍然只有 `/share/[token]` 那一条外链屏（清零 NEVER 靠往 exempt 里塞）。详见 `docs/trace/ENTRY-05.md`。
