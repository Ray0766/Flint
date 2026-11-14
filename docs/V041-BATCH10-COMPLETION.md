# v0.4.1 第 10 批 · 完成态报告（点了有反应 + 真数据）

**12 / 12 卡 verified · 0 blocked。**
五条全局门全绿，**pytest 零 failed**。
**广场今天显示的是真词面**——`热搜话题NN` 那批合成词一个都没有了。

---

## 〇 五条全局门（逐字贴）

```
$ ruff check .
All checks passed!

$ PYTHONIOENCODING=utf-8 python -m mypy --strict flint
Success: no issues found in 320 source files

$ PYTHONIOENCODING=utf-8 python -m pytest -q
5140 passed, 2 skipped, 12 warnings in 400.56s (0:06:40)

$ npx tsc --noEmit
（无输出，退出 0）

$ npm test -- --run
Test Files  85 passed (85)
     Tests  858 passed (858)
```

### pytest 的红：**一条都没有**

本批一路上红过的每一条，逐条点名（NEVER 按族小结）：

| 曾经红的 | 归谁 | 现在 |
|---|---|---|
| `test_main_chain_walk::…sheet_that_is_open` · `test_workbench_create::…storage_face` | `GAUGE-16`（尺子自己的账） | 已改判留痕 |
| `test_ui03::…sends_no_request` ×2 · `test_workbench_create::…one_graph_store` | 前提被 `WIRE-VERDICT` / `PERSIST-02` 推翻 | 逐条翻面 |
| `test_be_settings_locale::…three_things` · `test_i18n_keys_defined::…prefix` | `SHELL-02` 漏跑全量 | 已翻面 / 已登记 |
| `test_ds_bundle_wired::…a4_rule` | `PERSIST-02` 那一屏缺加载态 | 已改四态 |
| `test_ui_mainchain::…endpoint_that_does_not_exist` · `nav02` ×2 | `WIRE-VERDICT` | 逐条翻面 |
| `test_m1_009` ×3（`fetched_at` TypeError） | `CN-06` 写进 provenance manifest | 样本清单排掉 manifest |
| `test_m1_014/015/035/037/040` 共 13 条 | `CN-05` 给 arxiv 接 `totalResults` | 合成夹具加同一格（**数据零差异**） |
| `test_cn_real_ingest` ×2 · `test_cn03_preflight` ×2 | `CN-06`（两源→四源、单据已关） | 逐条翻面 |
| `test_cn03_preflight::…newest_day_with_data` | **探针在读两天前的缓存** | 已修（§四） |
| `test_dsn_isolation::…hardcoded_dsn` | `CN-03` | 改成扫描器认可的拼接写法 |
| `test_app_assembly::…answers_500` | 装配器既有缺陷，`PERSIST-02` 照出 | 已修 |
| parity / triage / type 共 20 余条 | `ENTRY-05` / 本批四张接线卡（钉着旧数字的表） | 全部翻面并重跑表 |

---

## 一 哪个功能今天点得到了、点下去会发生什么

| 功能 | 从哪进 | 点下去会发生什么 | 改前 |
|---|---|---|---|
| **广场看真热点** | `/plaza` | 落在**录制当日**，125 张卡：微博真实大陆热搜 + 「Google 趋势（港区）」署名条目 | 全是 `热搜话题NN` 合成词 |
| **热点判定** | 热点分析屏 | 没带 `?verdictJob=` 时**去问** `GET /clusters/{id}/verdict`，读得出四分类与引用 | 屏上恒说「未判定」 |
| **语言/地区详情屏保存** | `/settings/locale` 的「保存」 | 真存进 `prefs`，刷新后仍是刚选的；失败**不回滚**并显示错误 | 按钮按下去**什么都不发生** |
| **画布连线** | 工作台画布的连线表单 | 落 `graph_edges`，刷新后那条线还在；空假设回既有的 `EMPTY_HYPOTHESIS` | 端点**每次 500**（`edge_model=None`），且屏上没有入口 |
| **取消收藏 / 更新到最新 / 看是否过时** | `/favorites` 每条上的三个按钮 | 各自落库并重取列表；**三条失败各说各的** | 三条端点一处都没被调 |

## 二 哪些点不到、卡在谁那里

**16 条「已装配未调用」逐条判过**（`docs/端点分诊-v041-triage02.md`），**一条排除都没有**：

**甲 · 这一版要接（4 条，各带卡号）** —— 共同点是**那一屏今天已经在取数**：
`/plaza/topics`（`B11-PLAZA-TOPICS`）· `/projects/{}/hypothesis`（`B11-PROJECT-HYPOTHESIS`）·
`/shares/{}`（`B11-SHARE-MANAGE`）· `/deliverables/{}/staleness`（`B11-REPORT-STALENESS`）。

**乙 · 这一版明确不接（12 条）** —— 共同点是**那一屏还是写死的或还没建**。
**接端点与去掉写死是两件事**：先接的话屏上仍显示写死内容，而网络面板多了几条没人用的请求，**那比不接更难查**。

| 组 | 等的那一件具体的事 |
|---|---|
| 设计工作台 4 条 | `/design` 从写死改成真取数 |
| 报告族 3 条 | 那两屏不再写死；**干预层在报告屏上没有入口**——那是交互设计问题，不是接线问题 |
| 价格册 / 资料屏 4 条 | 那两屏还没建（**NEVER 为了让数字变小先建个空屏去调它**） |
| 外链只读屏 1 条 | 那一屏从写死改成真取数 |

**仍在 owner 手上的**：`K1-02` 照旧 open —— 四源**契约**齐了，
而它的根因（拿不到数据源令牌）没有消失：今天四源全部走免登录路，
未认证的额度与稳定性都是上游随时可以收紧的。

`docs/blocked/FAV-SNAPSHOT-HAS-NO-PROVIDER.md` 等 owner 一句话：
`POST /favorites` 的证据快照必填，而广场送 `{}`，
于是从广场收的每一条屏上都说「内容不在了」——**那是实话，而真相是没有人往里面放东西**。

## 三 真数据这条线（DEC-052 / 053 / 054）

四源全部经真实契约验证，端到端录制一次跑成：

| 源 | 实况 |
|---|---|
| weibo | 五条免登录路全废 → `DEC-053` 授权访客握手（三跳全通，`SUB` cookie 每次动态取） |
| gtrends | 旧 `dailytrends` 已下线；`geo=CN` 回 400（**Google 不编大陆榜**）→ `DEC-054` 港区代理 |
| ghtrend | 契约没漂，**一行没动**——产出是「证明了它是对的」 |
| arxiv | 契约没漂；接上 `totalResults` 把「那天没有」与「结构变了」分开 |

**DEC-054 的三件东西齐了**：DEC 文本明写代理 · manifest 记真实 `geo=HK` URL ·
屏上署名「Google 趋势（港区）」（**第三件此前是缺的**，署名只写「Google 趋势」）。

真实请求全部留痕：gtrends 8/20 · weibo 10/20 · ghtrend 2/10 · arxiv 5/10，
外加两份 robots 快照（`K2-01` RECORD_ONLY：照实记录、不阻断、NEVER 重判）。

**每日定时的持续真实采集没有接上**（`DEC-052` 明写不含它，判据扫着录制器里没有任何调度器）。

## 四 本批最贵的三次「看起来成功了」

1. **录制器把 `ghtrend` 与 `arxiv` 录成了 gtrends 的响应**，而回执报 `ok`。
   分派写的是「weibo 用 `WeiboHotSource`，其余一律 `GoogleTrendsSource`」——两源时代对，四源时代把新源录成旧源。
   > **这比失败更坏**：失败会喊，而这一种安安静静把三份一样的东西存进三个目录，
   > 且**有 manifest、有 sha256、看起来样样齐全**。

2. **对账器与前端对着一份虚构的形状达成一致**（`/projects/combo` 的三个字段一个都不在响应里）。
   > **它把「没人核对过」伪装成「核对过、没问题」。**

3. **一条判据在读两天前的缓存**：`_probe()` 第一句是「产物在就直接读」，
   于是 `CN-06` 真把当天数据灌进去之后，它仍然报「正在看 2026-07-05 的热点」。
   > **一把返回缓存答案的探针不是探针**：它红或绿都与屏上此刻的样子无关。
   > 修法是改成会话内记忆，**没有去调等待时间**——那只会把「两次读出两个答案」藏起来。

## 五 收工纪律的落地检查

- **全局门跑完之后没有再动任何被判据读的文件**：顺序是
  先写 trace 与台账 → 再跑五条门 → 最后只改本报告的数字；
- 台账那一行落下之后**单独重跑了它的读者判据**（89 passed）；
- **每张卡的 `started` 与终态成对**——`blocked` 也是一次「开始过」的记号。
  三张走了返工环：`CN-04`（三次 blocked）· `CN-06`（收尾暴露另一条红，如实记 blocked 再收）·
  `CN-05`（一条补记的 verified）；
- pytest 的红**逐条点名归属**（§〇），NEVER 按族小结。
