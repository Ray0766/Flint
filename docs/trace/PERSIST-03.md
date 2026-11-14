# PERSIST-03 · 模板表 + `template_solidify`——最后一个没消费者的作业

**结论**：迁移 `0024` 建 `templates`；注册表换 SQL 实现；`template_solidify`
接上消费者并从 `UnwiredKindReason` 移进 `WIREABLE_KINDS`——**那张表空了**。
`verify_cmd` 19 条全绿，`ruff` / `mypy --strict flint`（315 文件）全绿。

装载：`docs/steward/tasks-v041-b9.json#PERSIST-03` · `flint/jobs/dispatch.py` ·
`flint/design/solidify.py` · `flint/design/templates/registry.py` · `flint/api/design.py` ·
`flint/jobs/worker_main.py`（`build_handlers` 与两个既有 handler 的形状）·
`contracts_v04/models_v04.py#TemplateRecord #SolidifyResult` ·
`docs/trace/PERSIST-01.md`（同步桥的口径）
（实测装载 ≈ 30k tokens，预算 40k）

---

## 1 表名以 `DEC-048` 为准

`flint/design/templates/registry.py:39` 自述「SQL 实现随 E2 的 **`template_registry`**
表接入」，而 `DEC-048`（owner 2026-08-09 裁的）点名的是 **`templates`**，
本批出口判据也照那八个名字数。**以裁决为准**——那句注释是当时随手写下的设想。

（同一个形状在 `PERSIST-02` 上就不是这么轻的一件事：那里对不上的是**字段**
不是名字，所以那张卡停下报了 owner。）

## 2 号从 `0025` 改回 `0024`——**我先想错了**

第一版把本卡编成 `0025`，**给被阻的 `PERSIST-02` 保留 `0024`**，
理由写在当时的迁移 docstring 里：「trace 里四张迁移卡各是哪一号会错位」。

**那是错的。** 留号留出来的正是一个**跳号**，而本批 rules 写死
「NEVER 跳号也 NEVER 撞号」。仓里三把尺子当场判红：

```
tests/v041/test_persist_fav_share_prefs.py::test_the_migration_number_continues_without_a_gap
tests/v041/test_project_optimistic_lock.py::test_the_migration_continues_the_numbering
tests/v041/test_cluster_region.py::test_the_migration_continues_the_numbering
```

**它们是对的。** 「四张迁移卡各是哪一号」是 trace 上的记账方便，
「号段不许有洞」是写死的不变量，两者冲突时后者赢。
迁移改名为 `0024_templates.py`，`PERSIST-02` 的单据里那条「保留 0024」也一并改掉了
（**留着的话下一个人会照着它再留一次**）。

## 3 一个我自己埋的坑：判据把库丢在中间态

`PERSIST-01` 的 `test_the_migration_goes_down_and_up_again` 写的是
`downgrade 0022` → `upgrade **0023**`。单跑那一个文件没问题；
**同一次 `pytest -q` 里排在它后面的每一条用库的判据都被它带红**——
实测 20 条（模板表、全文列合规 `test_m1_016`、docstore 三族），
而那些红看起来全都像是别人的缺陷。

改成 `upgrade **head**`，并加一条断言 `_at_head()`：**判的是「没有中间态」这件事本身**。
（这条坑是本轮最值钱的一处：它把「我的判据只对自己负责」这个假设打掉了。）

## 4 改前 / 改后 / 为什么非改不可

### 4.1 新增

| 文件 | 是什么 |
|---|---|
| `migrations/versions/0024_templates.py` | `templates` 表，主键 `(template_id, version)` |
| `flint/design/templates/pgregistry.py` | `PgTemplateRegistry`（`available` / `all` / `append`） |
| `flint/jobs/template_solidify.py` | 作业消费者：取参 → 转调 `solidify_mock` → 发 `solidify_result` |
| `tests/v041/test_template_persist.py` | 19 条判据 |

### 4.2 既有文件

| 文件 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `flint/jobs/dispatch.py` | `UnwiredKindReason = {"template_solidify": …}` | `WIREABLE_KINDS` 多一条，`UnwiredKindReason = {}` | acceptance②。**空了 NEVER 等于可以删**——注释里写死了这一句，判据 `test_the_empty_unwired_table_is_still_a_live_mechanism` 守着机制还活着 |
| `flint/jobs/worker_main.py` | 9 个 handler | 10 个 + `template_solidify_deps` 字段 | 只改 `dispatch.py` 的话 `build_dispatch_table` 会当场抛 `IncompleteDispatchTable`——**接线不是把名字挪个位置** |
| `flint/api/app.py` | `TemplateRegistry(available=False)`；`model=None, event_model=None` | `PgTemplateRegistry(dsn=dsn)`；两个模型从 additive 层取 | 前者是本卡的产品；后者**非改不可**：改前它们用不上（没有存储面），而现在 `POST /design/templates` 会真的走到 `solidify_mock`，两个 `None` 会让固化在构造记录那一行炸成 500 |
| `flint/api/design.py` | 4 个碰注册表的 `async def` | 改成 `def` | 与 `PERSIST-01` 同一条：桥是阻塞的，在事件循环上调它会停住整条循环。**函数体一行未动**（它们本来就没有 `await`）。另外三条留在 async——它们各自要 `await` 一个注入的取数件 |
| `flint/design/templates/registry.py` | 三个函数形参写死 `TemplateRegistry` | 加 `TemplateRegistryLike` 协议并放宽 | `mypy --strict` 当场报。该文件 39 行自己写着「SQL 实现随表接入」——形参本来就该是形状 |
| `tests/v041/test_persist_fav_share_prefs.py` | 升到 `0023` 就停 | 升到 `head` + 断言 `_at_head()` | 见 §3 |
| `tests/v041/test_asm_02.py` · `test_asm_03.py` | 例子取 `min(UnwiredKindReason)` | 造一条本判据自己的声明 | 表空了 `min({})` 当场抛。那个写法本来就是为了不被接线进度带红，**它没预料到表会被清空**。改后量的是机制本身，与「今天还剩几条」脱钩 |
| `tests/v041/test_revalidation_wired.py` | `assert UnwiredKindReason`（非空） | `assert hasattr(..., "items")` | 「今天还剩几条」与「那张表被人清空了」在原断言上**长得一模一样**——这正是它该改的理由 |
| `tests/v041/test_design_generate_job.py` · `test_pricebook_scan_wired.py` | 钉 `{"template_solidify"}` / 遍历它 | 钉空集 / 遍历空表 | 同上，基线跟着事实走（两处 docstring 里都记着上一次同形状的改因） |
| `tests/v041/test_no_fake_empty.py` | `FAKE_EMPTY_PATHS = ("/design/templates",)` | 空元组 + `skipif` | `/design/templates` 毕业了（`PERSIST-01` 在那里留的注释预告过这一刻）。**缝没毕业**：两条直接打缝的判据照旧 |
| `docs/blocked/{两张单}` | 无机读状态行 | `**状态** open · …` | `HYG-01` 的 `test_every_sheet_declares_its_state_in_its_head` 判红——尺子是对的 |
| `docs/blocked/PERSIST-02-…md` | 「0024 保留」 | 改成「号不留了」+ 写清为什么那条纪律是错的 | 见 §2。**留着的话下一个人会照着它再留一次** |

## 5 作业侧那一处：`asyncio.to_thread`

worker 在事件循环上跑 handler，而 `registry.append` 换成 SQL 之后是阻塞调用。
`run_template_solidify` 里那一段因此走 `await asyncio.to_thread(solidify_mock, …)`。

`asyncio.to_thread` 是**标准库**——NEVER 为这一件事引一个新依赖（本批 rules）。
API 那一侧不用它：FastAPI 的同步处理函数自己就跑在线程池里。

## 6 自审（`self_review=true`）

**① 判据真实覆盖 acceptance**

| acceptance | 判据 |
|---|---|
| ① 表不存在 → not_provided → 固化置灰；Unwired 只剩这一条 | `test_the_templates_table_exists_now`、`test_the_templates_endpoint_no_longer_answers_not_provided` |
| ② 建表 + 接消费者，移完那张表就空了 | `test_template_solidify_moved_into_the_wired_kinds`、`test_the_unwired_table_is_empty_now`、`test_the_worker_wires_a_real_handler_for_it`、`test_the_handler_says_what_is_missing_instead_of_pretending_to_run` |
| ③ 固化按下去真提交并落库；成功后列表里看得到 | `test_solidifying_through_the_endpoint_lands_in_the_table`、`test_running_the_job_solidifies_and_lands_in_the_table`、`test_a_refused_solidify_says_why_and_lands_nothing` |
| ④ DESIGN-03 四态不倒 | `test_the_not_provided_seam_is_still_there_for_an_unavailable_registry` |
| ⑤ LLM 恒 fixture，respx 断言零真实出网 | `test_the_job_never_reaches_the_network`（固化是**确定性**文本变换，模型进来就不再可复现） |
| ⑥ 分派表仍覆盖判别联合全部成员 | `test_the_dispatch_table_still_covers_every_member_of_the_union` |
| 既有三条注册表纪律（去重按内容 / 版本 append-only / 归属隔离） | `test_the_same_content_never_makes_a_second_version`、`test_changed_content_appends_a_version_and_never_overwrites`、`test_my_templates_never_include_someone_elses` |

**先红后绿**：写完判据、未建表未写实现时 `19 errors`；实现完 `19 passed`。

**② 无冻结件偏离**：`contracts/` 与 `contracts_v04/` 四件一字未动。
`TemplateRecord` 的 `slots` 读回来转成**元组**（冻结件那一行写着「用元组是因为
插槽集合固化后不该被就地追加——那会绕过 checksum 绑定」）。

**③ 无禁用词**：新增与改动处六个词 0 命中。

**④ 复用断言在位**：`solidify_mock` / `register_template` / `list_templates` /
`to_slots` **一行都没重写**；判据 `test_changed_content_appends_a_version_and_never_overwrites`
与 `test_a_dangling_*` 系列都是**经由既有域函数**去打 SQL 件的，
这就是「复用在位」的可执行形态。

**⑤ 装载未超预算**：≈30k / 40k。

## 7 门

```
pytest tests/v041/test_template_persist.py -q     19 passed
ruff check . --no-cache                           All checks passed!
mypy --strict flint                               Success: no issues found in 315 source files
```

**全量 `pytest -q` 尚未在本卡收尾后重跑**——上一次全量（改这批基线之前）是
`18 failed / 4790 passed / 33 errors`，其中绝大部分是本节逐条修掉的那些
（33 个 error 全部来自「库被丢在中间态」，见 §3）。
下一轮开工第一件事 MUST 是重跑一次全量确认，**NEVER 拿这份未复跑的数字当结论**。

## 8 留给下游

1. **`PERSIST-04`**：迁移号接盘上当时最高的那一号（**不要再留号**，见 §2）。
2. **八张表进度 4 / 8**：`favorites` · `share_links` · `prefs`（`PERSIST-01`）+
   `templates`（本卡）。剩下四张里三张卡在 `PERSIST-02` 那张单上，
   `cluster_verdicts` 归 `PERSIST-04`。
3. **`SHIP-09`**：出口判据「`UnwiredKindReason` 空表」**本卡已达成**。
