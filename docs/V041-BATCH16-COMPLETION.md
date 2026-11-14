# v0.4.1 第 16 批（停机前收尾）完成态报告

> **本批只做两张卡 + 收尾**：`COMBO-WIRE-01` · `TAIL-01` · `SHIP-16`。
> 报告里凡是提到「能点通」的部分，只有第一段是本批接的；其余是此前批次的产出。

---

# 一、《回来时从哪接》（一页）

## ① 今天能点通到哪一步

**广场 → 工作台 → 「按你选的卡建项」→ 主题** 这一段**今天是通的**（本批修的就是这一步）。
逐屏截图（真浏览器 · 真栈 · 一步一张，1920×1080）：

```
.ui-probe/combo_wire/combo-plaza-1920x1080-light.png     ① 广场：55 张热点，选 3 张 + 一句假设 → 建项键亮
.ui-probe/combo_wire/combo-picked-1920x1080-light.png    ② 工作台左栏选 3 张 → 中栏「本次组合」列的就是那 3 条
.ui-probe/combo_wire/combo-typed-1920x1080-light.png     ③ 写一句假设 → 提交键从灰变亮
.ui-probe/combo_wire/combo-receipt-1920x1080-light.png   ④ 按下去 → **200**，屏上「建好了，生成了 N 条候选主题」
.ui-probe/combo_wire/combo-topics-1920x1080-light.png    ⑤ 主题页列出那 N 条（屏上列的 = 库里有的）
.ui-probe/combo_wire/combo-doc-1920x1080-light.png       ⑥ 右栏渲染真 Block（30 块，块型全在冻结件那八枚里）
.ui-probe/combo_wire/e2e.json                            每一步的数（发出去的卡 id / 回来的 id / 耗时 / 被拒的每一发）
```

**到这里为止是真的**（末次取证 2026-08-12）：`POST /projects/combo` 回 **200**
（**19.6 秒**，本地 `qwen3.6:35b-a3b` 真跑），建出 `proj-combof186e492d8` 与 **6 条主题**，
主题页列的 6 条与端点回的**逐字相同**（本批期间跑了三趟，每趟 19.6~33.9 秒 / 5~6 条主题——
条数是模型每次的产出，不是固定值）。

**一句要分清的话**：**后端那条链本身此前跑通过**（库里 18 份交付物是证据，
其中 14 份计划书是前几批真跑出来的）。今天断的是**「从屏上一路点下去」**这条路——
两者不是一回事，而 owner 要的是后者。

**再往后还断着，两段各有各的单**（NEVER 读成「广场到计划书全通了」）：

| 段 | 状态 | 卡在哪 |
|---|---|---|
| ① combo 建项与主题 | ✅ **本批接通** | — |
| ② 发起分析（Gate①） | ❌ | 作业一被消费就打**真实** github/arxiv，属事前必审；`DEC-057` 那个窗口只授权过一次 |
| ③ 成文（报告/计划书） | ❌ | `POST /projects/{id}/report` 要 `analysis_id`，而**没有一条从分析拿回它的路**（`ANALYSIS-ID-HAS-NO-PATH-FROM-AN-ANALYSIS.md`，owner 四选一待答） |
| ④ 看产物 | ⚠️ 半通 | 右栏能渲染真 Block，但要用 `?deliverable=` 手动打开——链自己交不出那个 id（`PROJECT-DOES-NOT-LIST-ITS-OWN-DELIVERABLES.md`） |

⑥ 那张图里的产物**不是本次 combo 的产物**，是库里此前真跑出来的一份——
`e2e.json#doc.note` 里如实写着这句。

## ② 还剩几张 open 单，哪几张归 owner

**21 张 open**（本批关掉 5 张：`COMBO-FAMILY-HAS-NO-PROVIDER-ANYWHERE` +
`TAIL-01` 的四张；又新开 1 张：跑门时抓到的 `UI07-FLAKY-AGAIN-ON-THE-DEFAULT-BODY`）。
其中**7 张写着「需要 owner 的什么」**——那 7 张是回来后**先看**的：

| 归 owner 的单 | 要 owner 一句什么 |
|---|---|
| `ANALYSIS-ID-HAS-NO-PATH-FROM-AN-ANALYSIS` | 四种口径选一种（这条**挡着主链第三段**） |
| `PROJECT-DOES-NOT-LIST-ITS-OWN-DELIVERABLES` | 项目总览那一列怎么变成「查出来的」而不是建项时写死的 |
| `REGENERATE-JOB-WRITES-NO-EVENTS` | 重写作业要不要按既有 `enter_state` 那条路补状态与事件 |
| `QUALITY-FAMILY-HAS-NO-BACKEND` | 这一族要不要在 V1 内做（今天右栏逐章恒「还没有判定」） |
| `REAL-GAP-NOTICES-HAVE-NO-HINTS-REF` | 「缺什么」那块的 hints 要不要落库 |
| `SIBLING-DELIVERABLE-ID-IS-NOT-IN-THE-CONTRACTS` | v4 说的两版互链要不要动冻结件（S2-1 触点） |
| `FOUR-REDS-ALREADY-ON-THE-FLOOR-BEFORE-PERSIST-01` | 四条历史红的处置 |

其余 14 张是**工程面**的（不必等 owner）：Gate① 取两遍 / 同文两 intent /
GitHub 免登录限速 / 六族改状态不写事件 / 三处取证样例 id 是占位 / 尺子读注释 /
金标回放缺库 / 港区计数说七 / 一次没抓到名字的前端红 / 三条候选源契约拿不到 /
上线前的抓取手续 / chart 与质量卡与 hints 无存储面 / 一条样例簇没有判定 /
**`UI-07` 那条两拍竞态（本批跑门时抓到的）**。

## ③ 下一批最该做的三件事

**一 · 把主链的第二、三段接通**（要 owner 先答两句）
> 理由：这是 owner 唯一真正想看的东西——「从热点到一份计划书」。
> 第一段今天通了，**它现在是链上唯一通着的一段**，后面两段各差一个决定：
> `analysis_id` 的口径（四选一），以及要不要再开一次真实网络窗口。
> 两句话答完，后面是纯工程。

**二 · 「提交了 → 产物是哪一份」那三条路**（不需要 owner 决定的那部分先做）
> 理由：第 14 批六张单说的是同一件事，本批又实测撞到一次——
> 单块重写**真的产出了 v2**（库里查得到），而 `jobs.state` 还停在 `queued`、
> 项目总览也列不出它。**产物是真的，屏够不着**。
> 这三条修完，每一条链的终点才在屏上看得见。

**三 · 清掉右栏那 9 发被拒**（`QUALITY-FAMILY-HAS-NO-BACKEND` + `REAL-GAP-NOTICES-HAVE-NO-HINTS-REF`）
> 理由：每打开一份真产物，控制台就有 1 条 503（quality）+ 8 条 404（`/hints/`，
> 因为 `hints_ref` 是空串）。**它们今天的行为是对的**（如实拒绝，NEVER 假装有），
> 但它是 owner 每次看计划书都会撞到的两处破绽，且都不必等谁决定。

---

# 二、五条全局门（逐字贴出）

```
① ruff check --no-cache .
All checks passed!

② mypy --strict flint
Success: no issues found in 323 source files

③ PYTHONIOENCODING=utf-8 pytest -q
5762 passed, 2 skipped, 12 warnings in 499.31s (0:08:19)

④ cd web && npx tsc --noEmit
tsc exit=0

⑤ cd web && npm test -- --run
Test Files  85 passed (85)
     Tests  858 passed (858)
  Duration  6.14s
```

**跑法两条（每批都要）**：`pytest` MUST 带 `PYTHONIOENCODING=utf-8`（不带的话 27 条
走子进程的判据假红）；**NEVER 同时跑两个 pytest**（共用 `flint_test`，会互相清空——
第 15 批实测过一次，报的是「clusters 表没有 region 列」，与真红长得一模一样）。

## pytest 的红逐条点名

**贴出去的那一遍是 0 failed。但它是第二遍——第一遍红了四条，四条都在这里点名。**

第一遍：`4 failed / 5758 passed / 2 skipped`（525.71s）。**四条全是本批引起的，
且没有一条是产品缺陷**——四条量的都是「源码长什么样」，而本批把源码的样子改了：

| 红 | 归属 | 为什么红 | 怎么改的 |
|---|---|---|---|
| `test_theme_toggle::test_an_explicit_choice_beats_the_system_preference_both_ways` | `TAIL-01` | **尺子读了注释**：它用 `text.index('[data-theme="dark"]')` 比先后，而我在 `colors.css` 的注释里解释「哪条规则管暗色」时写了这个选择器 → 量到注释的位置（4348 < 5265），判出「显式暗色写在 media 之前」这种假红 | 先剥注释再比位置 |
| `test_compose_e2e::test_the_demo_hands_the_queue_to_the_app` | `COMBO-WIRE-01` | 它比的是**字面量** `"create_app(DSN, redis_url=REDIS_URL)"`，而本卡给同一发调用补了 `combo_provider=` → 变的是那一行的**格式**，队列那条缝一个字没变 | 改判 AST：那一发 `create_app` 的关键字里 MUST 有 `redis_url` |
| `test_network_discipline::test_the_repository_has_no_unguarded_live_network_today` | `COMBO-WIRE-01` | 新建的 `harness/local_model.py:54` 造 `httpx.Client(...)` 没带 `transport=` → 守门器如实报「无护栏的真实外部请求」 | 进 `LIVE_COLLECTORS` 白名单并写明理由（本机 Ollama、localhost、零 key）。**名单反而短了一格**：这只客户端此前在 `demo_server` 与 `run_worker` 里各造一份，两处都在名单上 |
| `test_network_discipline::test_the_cli_exits_zero_on_a_clean_tree` | 同上 | 同一件事的 CLI 那一侧 | 同上 |

**三条的共同形状**：判据钉的是**源码的样子**（一行字面量 / 一个位置 / 一处客户端构造），
不是那件事本身。本批把源码的样子改了，它们就红——**红得对**；
改法是把它们瞄回那件事（AST / 剥注释 / 名单写明理由），
NEVER 把断言删掉或放宽成「有就行」。

## vitest 那一发红（**已开单，本批不修**）

跑门时 `vitest` 全量红过一条：

```
FAIL __tests__/app/ui07.test.tsx > UI-07 · 两轴正交（A3） > 屏上改一根轴，另一根原样不动
AssertionError: expected 'CN' to be 'FR'          （1 failed | 857 passed）
```

紧接着单独连跑三次 `18 passed × 3`；机器安静之后全量单跑 `858 passed`（就是上面贴的那一发）。

**机理是 `FIX-04` 已经证过的两拍竞态**，只是活在「默认回包」那条路上——
那条路上「等值」区分不了两拍（`FIX-04` 的关闭节自己写着「默认值那条用例看不出来」）。
**本批不修**（`no_new_fronts`），开单
`docs/blocked/UI07-FLAKY-AGAIN-ON-THE-DEFAULT-BODY.md`，
连同「那一次是与全量 pytest 抢机器时红的」一起记着——
`UI07-LOCALE-TEST-IS-FLAKY` 自己写过：**间歇红比稳定红更坏，它会训练人「重跑一遍就好」**。

---

# 三、本批做了什么（两张卡）

## `COMBO-WIRE-01`：把 combo 的 provider 插上

**这不是缺功能，是留了缝没插上。** `create_app` 早有 `combo_provider` / `combo_model`
两个参数，`demo_server.py` 自己的注释还写着怎么插——全仓就是没有一个调用方传过它。
于是 `POST /projects/combo` 在**所有**部署上都是 503，owner 在工作台屏上撞见的就是那一句。

| 改在哪 | 改前 → 改后 |
|---|---|
| `harness/demo_server.py#build_app` | `create_app(DSN, redis_url=…)` → 再带上 `combo_provider=build_local_provider(), combo_model=MODEL` |
| `harness/local_model.py`（**新建**） | 模型接入的**唯一定义处**：改前那三行在 `demo_server` 与 `run_worker` 里各写一份，combo 接进来就是第三份 |
| `flint/api/app.py` | 503 那句话不再猜原因（原话硬写「迁移里没有对应的表」——**对 combo 是假的**，表全在，缺的是模型） |
| `start-demo.ps1` | **零改动**。它那句「combo/Gate 走免费本地」今天变成真话，判据核的是那条**链**（脚本把 `$Model` 交给 `FLINT_FREE_TIER_MODEL`，combo 的模型名从那里来） |

**缝没拆**：不注 provider 时照旧 503 并点名 combo（阴性对照在判据里，进程内真发一次请求）。
**`web/` 下零字节改动**——开工前拍了 277 个文件指纹，判据逐个比。

## `TAIL-01`：清掉四张已答复的单

| 单 | 落地 |
|---|---|
| `--warn` 与 `DEC-060` 冲突 | 改名 **`--ochre`（赭）**，值 `#a3701c` 一个字不动；用途边界写死并各配判据（明色实测 **4.01**，够图形不够正文，挂到正文上判据当场红并报出这个数） |
| 广场上限与 `ENTRY-04` 冲突 | **卡面错、既有纪律对**。`test_plaza_multiselect_combo.py` 一个字没动（sha256 钉住） |
| 药丸条与吉祥物 26 行写死色号 | 搬进 `_ds/tokens/colors.css`，`globals.css` 只剩 `var()`；**搬的是位置不是值**（真浏览器量搬前搬后，元素层 12 项零差异） |
| `DEC-060` 措辞出处 | steward 认下措辞，`DECISIONS-v04.md` 一个字没改（append-only） |

搬完之后 `web/` 下除 `_ds/tokens/` 外**一个颜色字面量都不剩**，新的全仓判据**没有白名单**。

---

# 四、本批最值得记的两条

**一 · 判据比错了东西，被它自己抓到。**
「搬前搬后颜色没变」第一版比的是 token 文本，实测 11 个全不同——
差的是**格式不是颜色**：`globals.css` 过 Next 的 CSS 管线被压成 `#ffffffb8`，
而 `_ds/tokens/colors.css` 是 `web/public/` 下的静态文件，原样送到浏览器。
改成**元素层判逐字**（浏览器算出来的值，两条管线在这一层已经合流）+
**token 层判颜色**（规范化后比，并给规范化本身配阴性对照）。

**二 · 一改动就有一批判据在描述旧世界。**
combo 接通之后，四条既有判据当场红——它们钉的是「那一族恒 503」那个世界：
`test_wb_generate` 三条（终态取的是最后一条消息，而成了之后最后一条是「下一步还没接上」
的告知）、`test_eye05` 一条（同因）。**意图一个字没改，改的是量法**：
失败那一路照旧比服务端原话，成了那一路比**回执上的 id == 服务端回的 id**——
两路判的都是同一件事：屏上说的就是服务端说的。

另有四处是 `TAIL-01` 搬家连带的（多了一族故意不跟主题翻的固定色 / 复合值不能进
`parse_color` / 白↔黑被判成算术取反而它没有色相可翻 / **两条判位置的尺子读到了我写的注释**
——本仓这一类栽过六次，第七次在这里）。逐条理由写在 `docs/trace/TAIL-01.md#六`。

---

# 五、环境实况（回来时会再遇到）

1. **改完 `harness/` MUST 重起 `:8000`**：跑着的进程握的是改前的码。本批实测就是先停
   旧 PID（59248 / 63260）再起新的；
2. **combo 真跑一次 22~34 秒**（本地 `qwen3.6:35b-a3b`，出 5~6 个候选主题）。
   判据等的是「等待记号消失」，NEVER 等固定秒数——那量的是运气；
3. **重写那一路要 worker 在跑**（`python -m harness.run_worker`）。本批开工时它没起，
   于是取证探针拍到的是「提交了，产物没出来」——那不是缺陷，是栈少了一个进程。
   **worker 用完即停**：它的 gate1 注的是真 github/arxiv；
4. `scripts/ui_probe.py` 默认 URL 仍是 `:3001`，而 demo 前端在 `:3000`——
   不带 `--url` 直跑会得到「前端未运行」的假红。

---

# 六、这一批**没有**做的事（NEVER 记成做了）

- 主链第二、三段（分析 / 成文）**一个字没动**；
- 21 张 open 单**一张没做**（本批只关了已答复的 5 张，另新开 1 张）；
- 支付 / 免费额度仍是零实现；
- 广场空态那句 v4 原文里的「2~5」**没有改**（它被另一条已 verified 的 verbatim 判据钉着，
  改它是文案问题，如实登记在 `PLAZA-UPPER-BOUND-CONTRADICTS-ENTRY-04.md` 的关闭节里）。
