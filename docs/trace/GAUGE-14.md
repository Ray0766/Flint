# GAUGE-14 · 对账器的两个盲区

> v0.4.1 第 6 批第十六张。全量 `pytest -q` **4518 passed / 0 failed**。

## 装载清单

`tasks-v041-b6.json#GAUGE-14` · `docs/blocked/PARITY-BLIND-TO-PAGES-AND-UNLISTED-PREFIXES.md` ·
`tools/check_fe_be_parity.py` · `docs/端点分诊-v041.md` ·
`tests/v041/test_{endpoint_triage,fe_be_parity,parity_dynamic_path,types_complete,scanner_strips_comments}.py`。
约 16k tokens，**未超 40k**。

## 一、两个盲区，机制不同

| 盲区 | 机制 |
|---|---|
| **首段白名单** | `_ENDPOINT_LITERAL` 里写死 `plaza\|clusters\|projects\|…`——不在清单里的路径**永远扫不到** |
| **只扫 `web/lib/`** | `useScreenData("/account")` 在页面里、`designSession.ts` 的提交在组件里 |

**共同后果**：报告说「后端有、前端没人用」，而真相是「尺子没量到」。
**修法完全相反**——一个去接线，一个去修尺子；读到误报的人会去接一条已经接好的线。

## 二、白名单退役：宽扫 + 与真实路由表取交集

新增一族端点时尺子自动认得——**而人维护的那串前缀，永远慢一批**。
扫描面同时从 `web/lib` 扩到 `web/lib` + `web/app` + `web/components`。

## 三、宽扫带进的噪声，四道排掉（**三道是开工后加的**）

| 排掉什么 | 为什么 |
|---|---|
| 注释 / 测试 / mock | 既有两道，`GAUGE-10` 的剥注释不倒 |
| **`href`** | 导航不是调用。后端恰好也有 `GET /topics/{id}`——不排掉，一条只被链接的端点会被算成「在调」，**往反方向错** |
| **静态资源** | `_ds_bundle.js` / `messages/zh.json` 从 `web/public/` 取，**按定义**不在路由表里；不排掉会说「前端要一条后端没有的路」，而那根本不是一条路 |
| **`export type … from`** | 模块路径，不是端点（`./i18n/config`）。既有那道只剥 `import` |
| **跨字面量的路径片段** | 客户端拼 `` `/deliverables/${d}` + `/sections/${s}/regenerate` ``，扫描器一次只看一个字面量。整条同时也在调用面里，所以片段是纯噪声——不排掉会说「前端要 `/sections/{}/regenerate` 而后端没有」，**而后端有，只是前面还有一截** |

## 四、一次真返工：交集把尺子的另一半弄瞎了

第一版直接 `if path in backend_paths: calls.add(path)`——
当场把 `frontend_wants_missing_backend` **整类判空**：
前端想要一条后端还没有的路，那条路按定义就不在路由表里，
于是被自己的过滤器吃掉。**而它看起来是绿的（一条都不报）。**

改成：真实路由**恒收**，其余按**形状**判（至少两段或带参数）。
顺序也讲究——**NEVER 先形状后路由表**：那样一条真实的单段 API
（`/account`、`/billing`）会被形状判据先毙掉，而它明明在路由表里写着。

## 五、结果

```
改前  35 条：unused 32（其中 14 条是误报）· wants 0 · 类型两类 0
改后  36 条：unused 20 · wants 1 · field_mismatch 7 · untyped 8
```

- **12 条误报移出**（逐条点名判据钉住，只判「条数变少」不够——少的可能是别的几条）；
- **1 条 wants 是真的**：前端在调 `POST /workbenches/{id}/nodes`，后端只有 `…/edges`；
- **15 条类型缺口本来就在，只是量不到**——盲区修掉才第一次看见。

## 六、15 条类型缺口：立单，不在本卡修

补类型是 `web/lib/` 的活，超出本卡 outputs。且**它们不该混在一张卡里**：
修尺子与补类型是两件事，混着做的话，下一次尺子出问题时
没人分得清「是尺子又瞎了还是类型又缺了」。
单据 `docs/blocked/PARITY-WIDER-SCAN-REVEALS-FIFTEEN-TYPE-GAPS.md`。

## 七、动了六份既有判据（前提被本卡修掉）

- **分诊表**：A 类（14 条「尺子看不见」）**整类消失**——那些本来就不该在表上。
  三条按 A 类形状写的判据去掉 A；`test_class_a_entries_really_are_called`
  **整条删除**（留一条永远为真的判据比没有更坏，它占着位置像还有人在守）；
- **盲区那张单**：判据从「必须还 open」改成「必须已 closed，且表里记着被谁重算」；
- **条数记录**：从「卡面 33 / 实测 35」改成「32 → 20 的重算」，意图没变——
  换了数就要留下换数的记录，否则少掉的那 12 条就没有名字；
- **三条钉零的**：那个零在**盲的尺子**下是真的，在看得见的尺子下不再是。
  钉死一个过期的零，只会让下一次真正的修复被判成错；
- **`frontend_calls` 的四处调用点**：签名多了路由表参数。

## 八、verify

```
pytest tests/v041/test_parity_blind_spots.py -q  → 10 passed（含四条阴性对照）
pytest tests/v041/test_{endpoint_triage,fe_be_parity,parity_dynamic_path,
       types_complete,scanner_strips_comments}.py -q → 全绿
pytest -q（全量）                                  → **4518 passed / 0 failed**
ruff / check_line_endings                         → 全绿 / 220 个文件全是 LF
分诊表 + 对账表                                    → 重跑写回（20 条 / 36 条）
```

## 九、self_review

① 判据覆盖 acceptance 五条，含**四条阴性对照**（新前缀认得出 / 页面里看得见 /
注释不误报 / `href` 不算）与**一条反向守卫**（它没有变成「什么都不报」——
把 `frontend_calls` 写成「返回全部路由」也能让「误报消失」为真）；
② 零冻结件改动；③ 无禁用词；
④ 改动面：`tools/check_fe_be_parity.py` + `docs/端点分诊-v041.md` + 判据，
**全在卡上 outputs**；另改六份既有判据（第七节逐条记因）；⑤ 装载 ≈16k tokens。

## 十、留给下游

`SHIP-06` 收工前记得：本批新立了两张单
（`PARITY-WIDER-SCAN-REVEALS-FIFTEEN-TYPE-GAPS` 与它顺带记的
`/workbenches/{}/nodes`），要进完成态报告的「没做成的」那一节。
