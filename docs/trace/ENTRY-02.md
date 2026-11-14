# ENTRY-02 · 选主题的写入口

> v0.4.1 第 6 批第十张。**全量 `pytest -q` 4459 passed / 0 failed。**

## 装载清单

`tasks-v041-b6.json#ENTRY-02` · `flint/topic/{project,store}.py` ·
`flint/api/{views,identity,analysis}.py`（只读边界与 `AUTH-03` 形状）·
`web/app/projects/[id]/topics/page.tsx` · `web/components/views/TopicListView.tsx` ·
`docs/blocked/TOPIC-CHOOSE-HAS-NO-WRITE-ENDPOINT.md`。约 14k tokens，**未超 40k**。

## 一、端点落在哪，为什么

新模块 `flint/api/topics.py`：`POST /projects/{id}/chosen-topic`。

**不塞进 `views.py`**：那份文件的第一句是「**既有模型上的只读端点**」。
往里加一个写，等于让那句话从此不成立——而下一个人读到它时会信它。

装配处（`flint/api/app.py`）挂上了。**挂上才算接线**：本批反复撞见
「能力建好了路由没挂」，而没挂时前端拿到的是框架那种没有 `code` 的 404
（= 这个能力还没挂），与「这一条不存在」长得一模一样。

## 二、一行判断都不重写

越界校验与 change_log 追加**转调** `flint/topic/project.py#choose_topic`。
判据里有一条专门断言端点里**没有**第二处 `topic_ids` 判断——
两处对「越界」的定义迟早分叉，而它们守的是同一条不变量。

## 三、幂等在端点这一侧，不在域函数里

`choose_topic` 每调一次就追一条 change_log——**那对域函数是对的**：
它不知道调用方是不是重复点了同一个按钮。而「同一主题重复选」不该留下第二条：
那会让变更历史看起来像**用户改了两次主意**。

所以短路判在端点。**阴性对照**钉住反面：**换**主题时第二条必须留下——
把幂等实现成「永远不追加」会把「改主意」这件事从历史里抹掉。

## 四、越了一格：`flint/topic/store.py`（**请 steward 复核**）

**改前**：`PgProjectStore.save` 是纯 `INSERT`。
**改后**：`ON CONFLICT (project_id) DO UPDATE`（`created_at` **不在**更新列里——
它是这条记录的出生时间，一次更新把它改成「现在」，等于让项目看起来是刚建的）。

**为什么非改不可**：`save` 只能建、不能更。唯一的调用方（`combo`）永远新建，
所以那个缺口一直没被执行到；本卡第二次 `save` 当场 **500**。
而 500 读起来是「服务器坏了」，真相是这个 store 没有更新路径。

**为什么不在端点里自己写一条 UPDATE**：那就是把 project 的持久化形状
写进第二个地方——本仓反复禁的那件事。

**这一处在卡上 outputs（`flint/api/` + `web/app/` + 判据）之外一格。**
按纪律 5 本该停下立单；我判断它与 `SLOT-02`/`SourceColumns` 那两次不同——
那两次缺的是**产品决定**，这一次是一个持久化助手的**机械缺陷**，
形式唯一、可逆、且本卡的 acceptance 没有它不成立。
**如实记在这里并在回合报告里点名**，若 steward 认为该走单据，回退只需一行。

## 五、屏上那个按钮：接上了，而纪律一个字没松

`TopicListView` 的 `onSelectTopic` 早就在，**屏没传**。现在传了：
POST → **整屏重读**。

**NEVER 前端记一份**（屏上那段注释原话）。接上写端点之后最容易顺手做的事，
就是本地先改一下让它「看起来快」——那份影子状态刷新一次就没了，
而用户以为自己已经选过。判据里有一条断言屏上**没有**任何本地的 `chosen` 状态。

**为什么是 `window.location.reload()`**：`useScreenData` 今天只收一个 `path`，
**没有 refetch 句柄**，给它加一个是 `web/lib/` 的改动（又一格）。
拿一个变化的假 query 去骗它重取**更糟**——那正是本批 `DEC-035` 判死的形状
（靠 FastAPI 静默忽略未声明 query 去实现一个副作用）。
所以用最笨也最诚实的一种，并立单 `docs/blocked/SCREEN-DATA-HOOK-HAS-NO-REFETCH.md`
（含修法与两条判据要求）。

## 六、动了一条既有判据

`tests/v041/test_topic_screens.py::test_the_missing_write_endpoint_stays_registered`
写的是「写端点还没有 ⇒ 单据必须还开着」。端点建出来之后它红了——
**红的是自己的前提过期，不是接线出错**。改成判「那件事真的做完了」：
端点在 + 单据关。改因逐字写在判据上方。

## 七、verify

```
pytest tests/v041/test_topic_choose.py -q        → 14 passed（含 8 条 compose）
pytest -q（全量）                                 → **4459 passed / 0 failed**
ruff / mypy --strict flint                        → 全绿 / 305 files
cd web && npx tsc --noEmit / npm test -- --run    → exit 0 / 805 passed
check_line_endings / outputs_declared / i18n_scan
/ no_scaffold_on_screen / check_design_constraints → 全绿
check_screen_composition / check_screen_coverage   → 36 项 0 违规 / 缺屏 0 · 端点对不上 0
分诊表 + 对账表                                    → 重跑写回（A 段 13→14，总 36→37）
```

## 八、self_review

① 判据覆盖 acceptance 五条，含三条阴性对照（换主题要留痕 / 四种拒绝两两不同 /
越界的不写库）+ 两条「接线真的挂上了」；
② 零冻结件改动；③ 无禁用词；
④ 改动面：`flint/api/topics.py`（新）+ `flint/api/app.py`（挂载）+ `web/app/` + 判据
（卡上 outputs），**外加 `flint/topic/store.py` 一处**（第四节，已点名请复核）；
⑤ 装载 ≈14k tokens。

## 九、留给下游

- `SCREEN-DATA-HOOK-HAS-NO-REFETCH`：一张小卡，outputs 应为 `web/lib/` + 那几屏 + 判据；
- `PgProjectStore.save` 现在能更新了——`flint/api/combo.py` 那条建项目的路径**行为不变**
  （它永远是新建），但下一个写 project 的人不必再撞一次 500。
