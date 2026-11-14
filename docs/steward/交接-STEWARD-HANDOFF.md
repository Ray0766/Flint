# steward 交接件 · 上下文压缩后的自我复原

**写于** 2026-08-04 · **末次全量重写** 2026-08-12（owner 暂停项目约一周）
**为什么存在**：steward 的判断质量依赖大量**已验证的事实**与**自己犯过的错**。上下文一压缩，这两样最先被稀释——留下的是「语气还像总监理、但事实基础被冲淡」的东西，那比换个人接手更危险。
**用法**：压缩后、或新会话上岗后，**先读本文再答任何问题**。与本文冲突时以台账和代码为准。

> 与 `supervisor.md` §3 同构。那一节救过一次场，本文照抄它的诚实结构。

---

## 一、我自己跑过、可以直接引用的事实（**末次更新 2026-08-12**）

**全局门**（steward 亲自复跑，非转述）
- `pytest -q` → **5716 passed / 2 skipped / 0 failed**（549.91s，2026-08-12）
- 历次复跑都与 worker 报的逐字相符：4757 → 4934 → 5015 → 5042 → 5057 → 5140 → 5232 → 5280 → 5292 → 5376 → 5462 → 5716
- `mypy --strict flint` 323 文件 · `tsc` 退 0 · `vitest` 85 档 858 · `ruff` 通过（这四条**我未复跑**，worker 报的）

**冻结件哈希**（每次巡检亲验；**原件八批以来一位未变**）
| 文件 | sha256[:16] |
|---|---|
| `contracts/models.py` | `B760C2EEB4E96A96` |
| `contracts/protocols.py` | `C5664938E16469FF` |
| `requirements.lock` | `962D012D8CCBE3E6` |
| `assets/heldout_questions.yaml` | `A80C8C73AF03C8DB` |
| `contracts_v04/models_v04.py` | `00ED425D85A8C927` ← **2026-08-10 变过一次** |
| `contracts_v04/protocols_v04.py` | `DCB19E99463B06E4` |

> `contracts_v04/models_v04.py` 那次变动**合规**，我逐条查过：原件 `contracts/models.py` 里**没有 `Region` 这个别名**（只有 `region: str` 字段）；该文件自述「改动只能来自 v0.4 修订 ∨ **owner 变更**」而 `DEC-056` 正是 owner 变更；`tools/check_frozen_additive.py` 实跑 **exit 0**。
> **与 `PERSIST-02` 当初「改 contracts_v04 要停下报 owner」不矛盾**：那次是把必填改可空（**收窄语义**，校验器会拒），这次是纯加 Literal 成员。**分界线就在那个校验器上。**

**三把接通面的尺子**（2026-08-12 直跑）
- 可达性：`24 屏 · 入口 7 · 走得到 23 · 豁免 1`，**每一屏都走得到**
- 对账器：`前端要而后端没有 0` · `未装配 0` · `真漂移 0` · `前端没建类型 0`；剩 **15 条「已装配未调用」**（能力闲置，不是断线）

**库里的真数据**（asyncpg 直查 demo 库，2026-08-12）
`clusters 269` · `evidence_cards 1242` · `topics 8` · `projects 3` · `cluster_verdicts 2` · `deliverables 15`（**14 份真产物 + 1 份夹具**，每份 19~30 个正文块）· `blocks 350` · `favorites 3` · `workbenches 1` · `graph_nodes 1` · `templates 0` · `share_links 1` · `alembic 0027`

**广场今天是真的**（`GET /plaza/hot?day=2026-08-10`）
`region=CN` → 50 簇（真实微博热搜：马嘉祺严浩翔 / 蔡磊 / 贾冰 / 钟楚曦 / 豆包）
`region=HK` → 10 簇（港区繁体：馬國明 / 美食博覽2026 / 碧瑤灣）
`region=US` → 0 且 `in_scope=False`

**台账**：`docs/progress-v041.jsonl` **596 行**；事件分布 `started 294 · verified 281 · blocked 19 · skipped_by_owner 1 · review_failed 1`；末事件 `SHIP-15 verified`

**裁决**：`DECISIONS-v04.md` 水位 **DEC-060**，共 61 条，81358 字节

**批次标记**：`B2~B15` 全部落盘（第 1 批无标记，那时机制还没建）；`docs/WORKER.lock` **不在**

**三家 API**（真调用或列模型验证，key 值我从未看过）
| 目标 | 环境变量 | 验到哪一层 | 确认的模型 id |
|---|---|---|---|
| DeepSeek | `FLINT_DEEPSEEK_API_KEY` | **真调用**（HTTP 200 / 0.000116 元） | `deepseek-v4-flash` · `deepseek-v4-pro` |
| Anthropic | `FLINT_ANTHROPIC_API_KEY` | 仅 auth | `claude-sonnet-5` · `claude-opus-5` · `claude-fable-5` |
| OpenAI | `FLINT_OPENAI_API_KEY` | 仅 auth | `gpt-5.6-sol` 等 |
| 本机 | `FLINT_LOCAL_BASE_URL` | 端点通 | `qwen3.6:35b-a3b`（组稿与判定全走它，**零 key 零付费**） |

**真实源的真实契约**（`DEC-052/053/054` 窗口内实测，探测留痕在 `fixtures/_probe/`）
- **weibo**：五条免登录路全废（302 到访客系统 / 403）。唯一路 = 新浪**访客系统匿名握手**（两次 POST 取 cookie），三跳实测全通。真榜**首行是置顶行**（`icon-top`、无热度 span）——适配器认这一档，如实跳过不编热度。
- **gtrends**：旧 `dailytrends` 已被 Google 下线（404）；新 `trending/rss` 活着，但 **`geo=CN` 回 400**（Google 不编大陆榜）。`DEC-054` 因此走**港区代理**，`DEC-056` 又把它改成 **HK 独立区**。
- **github**：免登录搜索 **`x-ratelimit-limit: 10`（每分钟）**——真响应头读到的，是 `K1-02` 那张单的第一份真实证据。本版**不配 token**，接缝留在 `flint/evidence/search.py:46` 的 `auth_headers`（今天注空）。

**七项核心功能的实况**（owner 2026-08-12 点名的那七项）
| # | 功能 | 状态 |
|---|---|---|
| ① | 热点搜集（CN+HK） | ✅ |
| ② | 广场与卡片 | ✅ |
| ③ | 收藏 | ✅ 卡片形式与广场一致 |
| ④ | 入台 | ✅ |
| ⑤ | 模板工具（原 AI 设计工作台） | ⚠️ 跑通过 1 次，另有 3 失败 1 排队 |
| ⑥ | 热点分析 | ⚠️ 作业 done 9，判定只落 2 行 |
| ⑦ | 生成计划书 | ✅ 14 份真产物 |
| ⑧ | 计划书工作台（新） | ⚠️ **屏与三栏都在，「建组合」那一步 503** |

---

## 二、我没验过的（**NEVER 当成我签过字**）

1. `mypy` / `tsc` / `vitest` / `ruff` 四条门——我只复跑 `pytest`
2. **281 张 verified 卡的逐张实现质量**——我抽验过的只有：第 1 批注入占位生成器（9 failed / 9 passed，不空转）、F-05、F-11
3. `V0 files 前端设计/` 那 16 屏——**那个目录零测试文件**
4. `worker.md` / `supervisor.md` 的逐字复核——我改过它们，未通读校对
5. 15 条「已装配未调用」的端点**逐条**该不该接——只看过分诊表的总数
6. 那 14 份真产物的**内容质量**——我只数了块数，没读过正文

---

## 三、我判断错过的（**这一节最重要，压缩时优先保留**）

| # | 我说过 | 实际 | 教训 |
|---|---|---|---|
| 1 | 「跑那条常驻反例探针即可完成 B1 反空转验证」 | 不成立。它证明「尺子认得出多主」，不证明「线程真撞上了」 | **凭「有个探针在」下结论，没问「那个探针量的是不是同一件事」** |
| 2 | 终检抽样口径「`review_gate` 10 张」 | v0.4 没有那个字段，只有 `owner_review` 7 / `self_review` 51 | 照抄 M1 的字段名，没核 v0.4 的真件 |
| 3 | LEDGER-01 卡面「71 事件 / 60 卡」 | worker 实测 70 / 59——**它对我错** | 我的口径把非卡条目算进去了 |
| 4 | `Doc.content` 上限初拟 256 KB | owner 加码到 2 MB | 上限该按「挡异常」而不是「省空间」定 |
| 5 | 第 2 批建议加厚到 20~30 卡含候选③⑤⑥ | 查完文件面发现会撞终检读取面，**自己收回** | 先给建议、后查文件面，顺序反了 |
| 6 | 提议「判官一致率不达标就停下问 owner」 | owner 指出会卡死无人值守连跑 | 把「谨慎」写成了「停机」 |
| 7 | `DEC-030` 把出口写成「`backend_not_assembled` 归零」 | 归不了零——缺的是 `role_resolver` 而库里没有授权事实 | **判据是我写的，我写之前没查那四族缺什么** |
| 8 | `UI-01~11` 验收写「风格照蓝本重做」，判据是 HTTP 200 / 零报错 / 无溢出 / 两主题截图 | 四条全绿，而广场是个 **4072px 的裸 `<ul><li>`** | **我写的判据全是禁止性的。禁止性判据挡得住做错，挡不住没做** |
| 9 | owner 问「前端后端连上了吗」，我答连上了 | 22 屏里点得到的只有 6 屏 | **我量的是「端点回不回」，他问的是「点不点得到」** |
| 10 | 报「解引用鉴权方向反了」并据此开卡 | 半对。我用的 `self`/`demo` 都是**我编的 id**，404 是正确拒绝；真缺陷只有匿名回 200 | **拿编造的身份去探，把正确的拒绝读成缺陷** |
| 11 | 「收藏的数据早就有了，只是屏没渲染」 | 半对。快照有证据卡、**没有卡面**，标题那一格没有来源——worker 更正了我 | 从**完成态报告的一行字**推出结论，没去看快照里到底有哪些字段 |
| 12 | 探 `/design/*` 四条路径全 404 → 差点报「端点没挂」 | **路径是我猜的**。从 `openapi.json` 取真路由后，design 一族 7 条全挂全通 | 与第 10 条同族。**当场收回**——收回比坚持便宜 |
| 13 | `EYE-04` 判据写「无横向溢出」 | 对 `position: fixed` 的元素**恒绿**（fixed 溢出不撑文档 `scrollWidth`）。药丸条在 390 下右缘 471 > 390，而我自己只看了 1920 两张截图 | **判据要量的是「最右元素右缘 ≤ 视口宽」**；而且**我该看的那张图没看** |
| 14 | `GATE1-DEDUP` 出口写「往返数 MUST 等于不同 URL 数」 | **写错了层**：URL 在 searcher 内部算，而那张卡的射程是调用点，够不着 | 与第 7 条同族：**我写之前没查那一层够不够得着** |
| 15 | 第 14 批起跑令里没写 `DEC-059` 的独立原文块 | 前四条我都写了。worker 照抄工单原话、如实标出处、开单等我认 | **格式的一致性本身是一条纪律**，漏一次就要靠别人替我兜 |

**共同点**：十五条里**九条**是「没回到真件就下结论」（第 10、11、12 尤其）；三条是「判据写得能过 ≠ 事情做到了」（8、13、14）；第 9 条更进一步——**我量的那件事，根本不是 owner 问的那件事**。

**从这些错里长出来的、现在写在工单 rules 里的纪律**：
- `positive_criteria`：判据一律正向、带实测数值；**且要覆盖「显示的是不是对的东西」**，不只是「长什么样」
- `real_browser`：视觉判据打真浏览器真栈，NEVER 用组件快照冒充整屏
- `stale_premise`：遇到「因为 X 所以不做」的注释，**先核 X 今天还成不成立**
- 全局门跑完之后 **NEVER 再动任何被判据读的文件**；真要动，重跑

---

## 四、当前局面（2026-08-12，owner 暂停约一周）

**做到哪了**：v0.4 封版 + 终检完成；**v0.4.1 跑完 15 批**（第 1 批 7 · 第 2 批 89 · 第 3 批 25 · 第 4 批 20 · 第 5 批 18 · 第 6 批 18 · 第 7 批 12 · 第 8 批 11 · 第 9 批 16 · 第 10 批 12 · 第 11 批 8 · 第 12 批 5 · 第 13 批 6 · 第 14 批 10 · 第 15 批 8）。

**主链已经全线跑通过**：热点 → 卡片 → 组合 → 主题 → 分析 → 判定 → 报告 → 计划书，每一段都有真产物为证（**14 份计划书**是最硬的那个证据）。

**唯一卡住的一处**：`COMBO-FAMILY-HAS-NO-PROVIDER-ANYWHERE`——`harness/demo_server.py:265` 调 `create_app(DSN, redis_url=REDIS_URL)` **没传 `combo_provider`**，于是 `POST /projects/combo` 在任何部署上都 503。**缝是留好的**（`app.py:459` 有参数、`:568` 有 `or _UnconfiguredProvider("combo")`），demo 自己 `:281` 的注释还写着怎么插。**这是「留了缝、没插上」，不是缺功能。** 另有一句假话：`app.py:424` 的通用消息硬写「迁移里没有对应的表」——对 combo 是假的（表全在）。

**open 单 25 张**，按类分：
- **归 owner 的 2 张**：`SIBLING-DELIVERABLE-ID-IS-NOT-IN-THE-CONTRACTS`（受众分叉「两版互链」语义在、字段不在，属 S2-1）· `K2-COMPLIANCE-BEFORE-LAUNCH`
- **steward 已答复、等落地的 4 张**：`WARN-TOKEN-NAME-CONTRADICTS-DEC-060`（改名 `--ochre`，值不动，用途边界要写死：4.01 够图形不够正文）· `PLAZA-UPPER-BOUND-CONTRADICTS-ENTRY-04`（卡面错、既有纪律对）· `NAV-MASCOT-COLOURS-ARE-A-SECOND-SOURCE`（26 行写死色号搬进 `_ds`）· `DEC-060-TEXT-IS-STEWARD-AUTHORED-OPTIONS`（措辞我认下）
- **工程面 19 张**：其中最要紧的三条形状——`SIX-FAMILIES-ADVANCE-STATE-WITHOUT-AN-EVENT`（作业失败不写事件，**屏上一直转圈**）· `GATE1-SAME-TEXT-TWO-INTENTS` + `SEARCHER-SCOPE`（searcher 实例活整个 worker 生命周期，`now` 冻在构造那一刻 → `fetched_at` 全是 worker 开机时间）· `ANALYSIS-ID-HAS-NO-PATH-FROM-AN-ANALYSIS`（`POST /projects/{id}/report` 要 `analysis_id`，而库里没有 analyses 表、没有从分析拿到它的现成路）

**三角色**：worker(`worker.md`) / supervisor(`supervisor.md`) / steward(`docs/steward.md`)；测试库 worker=`flint_test`、supervisor=`flint_review`。
**§9.1 那个坑真被踩过一次**：两个 pytest 并跑共用 `flint_test` 互相清空 → 假红「clusters 表没有 region 列」，单跑全绿。**假红长得和真红一模一样，唯一能分开它们的是「我刚才是不是同时跑了两个」。**

**`docs/steward/` 曾被两个会话同时写**（第 15 批工单是另一个会话出的）。今天没撞车（新文件），但**两边同时改 `tasks-*.json` 会是静默覆盖**——下次要先说清谁持有这个目录。

---

## 五、盘上文件地图（压缩后靠它复原，不靠记忆）

| 文件 | 是什么 |
|---|---|
| `docs/steward.md` | 我的角色指令（§1.1 压缩复原纪律 · §3 写入边界） |
| **`docs/steward/巡检.jsonl`** | **我的巡检台账**（append-only；**压缩带不走的记忆**，26 条） |
| `docs/progress-v041.jsonl` | 15 批共用的进度台账（有 BOM，须 `utf-8-sig`） |
| `docs/steward/tasks-v041-b{2..15}.json` | 各批机读真相 |
| `docs/steward/起跑令-*.md` / `常备连跑工单-*.md` | 各批可粘贴文本（loop 版：粘一次自转，DONE 标记退出） |
| `docs/V041-BATCH{1..15}-COMPLETION.md` | 各批完成态报告（worker 写的） |
| `docs/怎么测-v041.md` | **给 owner 的**：七项逐条「点哪里 / 该看到什么 / 看不到时是谁的问题」 |
| `DECISIONS-v04.md` | 裁决史，水位 `DEC-060` |
| `docs/blocked/*.md` | 25 张 open 单，每张顶部有机读状态行 |
| `docs/research/对标审阅-2026-08.md` | 12 仓 A 档对标（62KB）——**结论：全网没人做出我们的中间关节** |
| `tools/check_reachability.py` · `check_fe_be_parity.py` · `check_frozen_additive.py` | 三把尺子 |
| `.ui-probe/eye04/` · `eye05/` · `favcard/` | 真浏览器截图取证 |
| `前端设计/` | owner 给的蓝本：`Anime navbar live demo/`（导航条）· `ai工作台/Flint 设计台 v3.dc.html`（计划书工作台）· 3D 卡片轮播 · 404 页 · 热点线索卡堆叠 等 |

---

## 六、压缩后的复原动作（**按序，不可跳**）

1. 读本文全文
2. 读 `docs/steward.md`（角色指令）
3. 读 `docs/progress-v041.jsonl` 末 20 行（`utf-8-sig`）—— **台账优先于任何叙述，包括本文**
4. 读 `docs/steward/巡检.jsonl` 末 5 行
5. 跑一次越界检查（见下）
6. **然后才回答 owner 的问题**

**越界检查（一条命令，六个文件）**：
```powershell
& ".venv\Scripts\python.exe" -c "import hashlib,os,datetime;prot=['contracts/models.py','contracts/protocols.py','requirements.lock','assets/heldout_questions.yaml','contracts_v04/models_v04.py','contracts_v04/protocols_v04.py'];[print(f'{p:36} {hashlib.sha256(open(p,\"rb\").read()).hexdigest()[:16].upper()}  {datetime.datetime.fromtimestamp(os.path.getmtime(p)):%m-%d %H:%M}') for p in prot]"
```
对照值见 §一那张表。**对不上就是越界，立刻报 owner。**

**打真栈之前 MUST 先核 `:8000` / `:3000` 的 PID 与启动时间**——旧进程冒充过判据的对象**三次**。
**跑 `pytest` MUST 带 `PYTHONIOENCODING=utf-8`**；**NEVER 同时跑两个 pytest**（共用 `flint_test` 会互相清空）。

---

## 七、停机状态与恢复（2026-08-12 起约一周）

**停机时的盘面**：无 worker 在跑（`WORKER.lock` 不在）、`B15-DONE` 已落盘、五条门全绿、冻结件全线未变。
**本机栈**：docker（postgres:55432 / redis:56379）· 后端 `:8000` · 前端 `:3000` · worker + cron。**一周不用的话跑 `stop-demo.ps1`**（数据留着，`start-demo.ps1` 秒起）。

**恢复时第一件事**：走完 §六 六步，然后看两处——
1. `docs/blocked/COMBO-FAMILY-HAS-NO-PROVIDER-ANYWHERE.md` 是否已关（那是产品能不能点通的那一处）
2. `docs/progress-v041.jsonl` 末事件是不是 `SHIP-15 verified`（是 = 停机时的样子没动过）

---

## 八、给压缩后的我自己一句话

**说不准就说不准。** 第一、二节的分界线是我最值钱的东西——把「我跑过的」说成「我知道的」，或者把「别人报的」说成「我验过的」，比忘掉细节危险得多。owner 依赖的不是我记得多少，是我**分得清哪些是我验的**。

第三节那**十五条**错，九条是「没回到真件就下结论」，三条是「判据写得能过，而过了不等于做到了」，一条是「我量的那件事根本不是 owner 问的那件事」。
压缩之后如果只能留一段，留那一段。

**还有一条这半个月学到的**：**收回比坚持便宜。** 第 12 条错我是当场收回的——探错了路径、拿到 404、话已经说出口，改口只花一句；不改口的话，worker 会照着我的错结论去「修」一个没坏的东西。
