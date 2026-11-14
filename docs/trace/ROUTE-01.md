# ROUTE-01 · 路由归属：`/deliverables/{}/render` 被两个模块注册

**卡** `docs/steward/tasks-v041-b4.json#ROUTE-01` · **cycles 1（oneshot）** ·
**self_review = true** → §5 · **owner_review = true** → §6 · **依赖** `WIRE-11`

## 1. 装载清单

卡面 ROUTE-01 · `docs/blocked/RENDER-ROUTE-CLAIMED-BY-TWO-MODULES.md` ·
`flint/api/deliverables.py` 的 `render` 与 `DeliverableApiDeps` ·
`flint/api/pack.py` 全文 · `flint/api/app.py#KNOWN_COLLISIONS` ·
`tests/v041/test_app_assembly.py` 的四条冲突判据 ·
`tests/m4/test_m4_010.py` / `test_m4_028.py` / `tests/v041/test_be_pack_content.py` ·
`eval/export_gate.py`。约 16k tokens，预算 40k 以内。

## 2. 归属：赢家不是「挑一个」，是把输家的门也接过来

owner 裁决 `deliverables.py` 赢（它管五种 fmt；反过来选会让 markdown/html/pdf/docx
四种全部落到只认 pack 的处理函数）。但**只删路由是不够的**：

`pack.py` 的 render 身上有一样赢家没有的东西——**M4-027 三与门**
（blocking 审查 ∧ DagReport ∧ registry 门）。只把它删掉的话，
`fmt=pack` 会变成一条**不过导出门的出件路**，那比路由撞车严重得多。

所以本卡做的是四件事，而不是一件：

| 做了什么 | 结果 |
|---|---|
| `pack.py` 删掉那条 route 声明 | 源码里不再有两个模块抢同一条路径 |
| 三与门搬进赢家（`pack_gate_inputs`） | 门过 → 200 zip；门拒 → 409 带 violations 分类 |
| 门禁没注入 → **503 明说** | 「没配门禁」NEVER 等于「门禁放行」 |
| `KNOWN_COLLISIONS` 清空 | 登记是临时处置，解掉才是收工 |

`GateInputs` 这个类型**留在 `pack.py`**、赢家 import 它——
同一份真相，不是抄一份。单子当初估「第 3 种改动面最大」，
实测只多了一条 `import`：判定函数本来就在 `flint/spec/export_gate.py`，谁都不拥有它。

## 3. 挂载顺序 NEVER 用来保证语义

FastAPI 对重复注册**不报错**，先挂的先匹配。于是这处冲突的行为，
取决于 `app.py` 里两行 `assembler.add(...)` 的先后——
改一次顺序就换一种行为，而没有任何东西会说话。

本卡的核心判据 `test_no_path_is_claimed_by_two_modules` 判的是**源码里的注册面**，
不是装配后的结果：装配后只剩一条是「谁赢了」，而两个模块都写着那条路径这件事
本身就是下一次静默遮蔽的材料。

## 4. 一处功能确实没了（不是等价替换）

`pack.py` 的 `?fmt=markdown`——CLAUDE.md 单文件预览，**带门禁**。
赢家的 `fmt=markdown` 是 Block 树渲染，两种 markdown 在一条路径上放不下。

内容仍拿得到：`GET /deliverables/{id}/pack` 逐章给。
**但那条路不过导出门**（`pack.py` 自己的口径：「看内容不是导出」），
它走的是归属判定（`X-User-Id` 对不上就 404）。

`tests/m4/test_m4_028.py` 里那条判据改成量「内容还拿得到」，
并在 docstring 里写明**这不是等价替换**——NEVER 让它读起来像没损失。
要把带门禁的单文件预览接回来需要一个新的 fmt 值，见 §6。

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_render_route_owner.py -q → 12 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 301 source files
            pytest -q               → 4026 passed（WIRE-12 收卡时 4014，本卡 +12）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① deliverables.py 赢、pack.py 的 `/pack` 保留 | `test_the_pack_content_path_survives`、`test_pack_module_no_longer_registers_the_render_path`、`test_a_missing_builder_still_says_unavailable`（挑赢家的理由之一原样保留） |
| ② 同 method+path 多模块注册即红，NEVER 靠挂载顺序 | `test_no_path_is_claimed_by_two_modules`、`test_the_assembled_app_has_exactly_one_render_route`、`test_the_duplicate_detector_still_bites`（**阴性对照**：造一对真的抢同一条路径的模块） |
| ③ fmt=pack 仍通、经三与门、409 与 200 都覆盖 | `test_pack_export_passes_the_three_way_gate_and_returns_a_zip`(200)、`test_a_refused_gate_blocks_the_export_with_its_violations`(409)、`test_a_missing_gate_refuses_instead_of_exporting`(503)、`test_the_other_four_formats_are_untouched` |
| ④ 关闭那张单 | `test_the_ticket_is_closed` + 单子正文写明四件事与那处功能损失 |

**② 改既有文件八处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `flint/api/deliverables.py` | 加 `pack_gate_inputs` 缝；`fmt=pack` 分支先过三与门 | **卡上 outputs**。不接的话赢家那条是**不过导出门的出件路** |
| `flint/api/pack.py` | 删 render 路由（含随之无用的四个 import 与 `deliverable_store`）；文件头重写 | **卡上 outputs**。留着不挂只是把静默遮蔽换成死代码 |
| `flint/api/app.py` | `KNOWN_COLLISIONS` → `()` | 冲突解掉了，登记面不空等于说「还有一处静默遮蔽」 |
| `tests/v041/test_app_assembly.py` | 三条冲突判据翻面（§7） | 它们钉的是「有一处已登记冲突」，本卡把那处解了 |
| `tests/m4/test_m4_010.py` | 两处注入 `pack_gate_inputs=clean_gate` | 门变成必经之路后，不给输入就是 503。**给的是放行输入**——本文件量的是 zip 出件本身 |
| `tests/m4/test_m4_028.py` | client 换成赢家；markdown 那条改量 `/pack`；同门那条只判出件 | 它建的 app 里那条路由没了（§4） |
| `tests/v041/test_be_pack_content.py` | 「`pack.py` 里 render 一行没动」→ 在**赢家**身上量导出面，并反向断言输家不再注册 | 继续判本模块的话，这条会**逼着人把冲突再造回来** |
| `eval/export_gate.py` | 建 app 换成赢家 | 它量的是门的四种情形，而门已经在赢家那边跑；不换就是量一条收不到请求的路 |

`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；**未新增依赖**。

**③ 变异考 6 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 把冲突原样加回 `pack.py` | 红 4 条，报出是哪两个模块 |
| ② 没配门禁 = **悄悄放行**（不是崩，是照常出件） | 红，实测拿回一个 zip（`PK\x03\x04`）而判据要 503 |
| ③ 门拒了照样出件 | 红，同样拿回 zip |
| ④ 409 不带 violations | 红（`KeyError: 'detail'`） |
| ⑤ 登记面又填一条 | 红 |
| ⑥ 三与门误伤 markdown | 红——**报告导出被 pack 的门拦住是另一个 bug**，这条钉住它 |
| ⑦ 假变异对照：末尾一行注释 | 全绿 12 passed |

②' 是重跑的：第一版变异只删守卫不删调用，红在 `TypeError: NoneType not callable`——
那是**崩**，不是「悄悄放行」。崩掉的红与咬住的红在返回码上一样，
所以重写成真正的放行路径再量一次。**这是本批第二次靠核对红的理由发现假红**
（上一次在 `WIRE-12`）。

**④** 装载约 16k tokens；**⑤** 禁用词六词 0 命中。

## 6. owner_review

**一处功能没了，且我 NEVER 自己发明替代品。**

`?fmt=markdown` 的 CLAUDE.md 单文件预览（带三与门）随那条路由一起消失。
接回来需要一个**新的 fmt 值**（比如 `fmt=pack_markdown`）——那是 API 口径，
不是 worker 该发明的。三条路：

1. **不接**（当前）：要看 pack 内容走 `/pack`，逐章 JSON，不过导出门。
   代价：没有「带门禁的纯文本预览」这个东西了；
2. **加 `fmt=pack_markdown`**：语义完整，与出件同门。代价：fmt 枚举多一个值，
   前端契约与文档要跟着改；
3. **让 `/pack` 也过三与门**：与 `pack.py` 自己写的「看内容不是导出」冲突，
   我不建议——那句话是对的。

**我的看法是②**，但它是一条 API 口径，值不值得单开一卡由你定。

另：`PackApiDeps.dsn` 现在没人读了（那条路由删掉后 `PgDeliverableStore` 不再需要）。
删它要动四个构造点（`app.py` / 两个 m4 测试 / `eval`），**本卡没删**——
留一个没人读的字段，时间长了会被当成「配了就生效」，与 `WIRE-10` 的
`FLINT_EMBED_MODEL` 是同一类问题，一并请你裁。

## 7. 三条被我翻面的等值判据

| 判据 | 改前钉的 | 改后钉的 |
|---|---|---|
| `test_each_known_collision_names_a_winner_and_says_why` | 「必须非空——实测有一处，别把它扫掉」 | `== ()`：登记是临时处置，解掉才是收工 |
| `test_a_registered_collision_does_not_raise` | 登记那处不报错 | **登记面空了之后，那句 `>= 空集` 恒真**——判据会空转，改成量「二十几个模块装得起来」 |
| `test_the_shadowed_module_is_not_silently_dropped` | 遍历登记面 | 空登记时循环不跑了，补两条直判（赢家那条在、`/pack` 也在） |

第二条是本卡最该记的一处：**把一处冲突解掉，会让原来盯着它的判据变成空转**——
「绿」从此不再有内容。翻面时要问的是「这条判据现在还量着什么」，
而不是「它绿不绿」。

## 8. 登记未做

1. **`fmt=pack_markdown` 没加**：见 §6，等 owner 一句话。
2. **`PackApiDeps.dsn` 没删**：见 §6。
3. **`pack.py` 现在只剩一条端点**：模块名与文件头已随之改写，
   但它与 `deliverables.py` 是否该合并，超出本卡范围。
4. **`fmt=pack` 在装配后的应用里仍是 503**（`create_app` 既没注入 builder
   也没注入 gate inputs）——那是部署面的事，`WIRE-10` 已有同类登记。
