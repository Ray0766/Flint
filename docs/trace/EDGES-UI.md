# EDGES-UI · 画布连线：端点在、表在，而那条路自己也没通

**结论**：修好取数路两处**真缺陷**（`edge_model=None` → 每次 500；
同步 store 没挪出事件循环），再把连线交互放上画布。
对账器 `backend_unused_by_frontend` **17 → 16**，`field_mismatch` 0。
`verify_cmd` 9 条全绿。

---

## 1 卡面说一件事，实况是两件

卡面：「端点已装配、`graph_edges` 表已建，**缺的是画布上那个交互**」。

**实测那条路自己也没通**：

1. `create_app` 注的 `edge_model=None` → `add_edge` 拿 `None` 当构造器调
   → `POST /workbenches/{id}/edges` **每一次都 500**。
   接了画布也照样存不下，而屏上会说「没存下」，**排查的人会去查画布**；
2. 处理函数是 `async def`，而 `PERSIST-02` 把图换成 `PgGraphStore` 之后
   它每次抛 `BlockingCallOnEventLoop`。`PERSIST-02` 给 `workbenches.py`
   包了 `run_in_threadpool`，**漏了这一个**——那时这条路上的 store 还是内存件，
   包不包都跑得动，所以漏掉时没有任何东西会红。

修完实测：`500` → `422 VALIDATION_FAILED`（悬空边）/ `422 EMPTY_HYPOTHESIS`（空假设）。

## 2 三种失败各说各的

| 失败 | 用户该做什么 |
|---|---|
| 空假设 | 补一句「为什么把这两样连起来」 |
| 悬空边 | 去看两端选对没有 |
| 没存下 | 重试 / 查后端 |

空假设走**既有的那一个** code（`EMPTY_HYPOTHESIS`）——
`docs/blocked/EMPTY-HYPOTHESIS-TWO-CODES.md` 定过一次，**NEVER 再分叉出第二个**。

## 3 存不下 NEVER 把线留在画布上

与 `LocaleSettings` 那条「NEVER 回滚成旧值假装成功」是**同一条纪律的两个方向**：
那边禁「失败了把屏改回去」，这边禁「失败了把屏留在新样子」——
共同点是**屏上显示的东西没有依据**。

落法：成功之后**重取整张图**，而不是前端自己把线画上去。
判据钉住全程 NEVER 出现 `setGraph`。

## 4 本批第三次撞「对账器只认 `export interface`」

`EdgeSaved` 写成了 `export type`，于是它匹到了另一个**四字段**接口，
报「少了 `graph_id`」——而这份类型五个字段都在。
`PERSIST-02` 与 `FAV-WRITES` 各撞过一次，所以这一条写进了**源码注释**而不是只写 trace。

另两处同类（本轮 `FAV-WRITES` 记过）：方法穿过 helper 后扫描器只看得见默认 GET；
模板串里换一行会把路径切成 `/favorites/${`。

## 5 判据缺一步：`edges-owner` 不在 `users` 里

读那张图要比一次归属，`check_user` 会去 `users` 表查——不种那一行报的是
401 `IDENTITY_UNKNOWN`，**而那与本卡要量的东西无关**（`PERSIST-02` 那轮踩过同一处）。

种了就收：`graph_edges` / `graph_nodes` 都有外键指向 `workbenches`，
不收的话别的判据清表时撞外键——**红会出现在别人的文件里，而根因在这里**
（`WIRE-VERDICT` 那轮实测：全量从 0 failed 变成 6 failed / 18 errors）。

## 6 改前 / 改后

| 文件 | 改前 | 改后 | 为什么 |
|---|---|---|---|
| `flint/api/app.py` | `edge_model=None` | `_graph_edge_model()` | §1-1 |
| `flint/api/graph_edges.py` | 直接调同步 store | `await run_in_threadpool(partial(add_edge, …))` | §1-2 |
| `web/lib/edgesClient.ts` | 不存在 | 三态结果（空假设 / 悬空 / 没存下） | §2 |
| `GraphWorkbench.tsx` | 只画节点与闸门 | +连线表单（不传回调就不渲染） | §3 |
| `web/app/workbenches/[id]/page.tsx` | 只取数 | 连完重取 | §3 |
| `web/messages/{zh,en}.json` | — | 各 +7 | 表单与三条措辞 |

## 7 门

```
pytest tests/v041/test_edges_ui.py -q   9 passed
ruff check . --no-cache                 All checks passed!
npx tsc --noEmit                        0
对账器：backend_unused_by_frontend 16（改前 17）· field_mismatch 0
分诊表：B 类 13 → 12
```
