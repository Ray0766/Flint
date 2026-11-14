# 图谱工作台的取证样例 id 库里没有，于是那一屏只被量到过「没有这张工作台」

**状态** open · 2026-08-12 · `WB-01`

不阻断（声明已按今天的实况改对）。本单要的是**把图真的画出来的样子量一次**。
关联 `assets/screen_composition.json#/workbenches/[id]` · `PERSIST-02` ·
`docs/blocked/NAV-BAR-OVERFLOWS-AT-390.md`（同一类：取证缓存不会自己失效）。

## 实况

`assets/screen_composition.json` 里这一屏的样例 URL 是

    http://localhost:3000/workbenches/wb-placeholder

`wb-placeholder` **库里没有**。实测（2026-08-12，真栈）：

    STATE   : not_found
    屏上文字 : 「工作台 wb-placeholder」「没有这张工作台」
    类名     : workbench__error

而库里**真有**一张：`wb-87be216d6b64`（`owner_id=demo-user`,
`seed_cluster_id=c-20260810-000`，建于 2026-08-10）。

## 那条声明本来写的是另一件事，而它已经过期

改前的 `why` 是

> 「`GET /workbenches` 未建，本屏一个请求都不发并如实标」

`PERSIST-02` 建齐了 `workbenches` / `graph_nodes` / `graph_edges` 三张表、
让 `POST /workbenches` 落库、并新建了 `GET /workbenches/{id}`——
**那句话从那天起就是假的**。屏真的在取数，只是取的那个 id 不存在。

没人发现，是因为取证结果落盘之后**永不重拍**：
`_observe()` 改前只判「文件在不在」。`WB-01` 给它补了按声明指纹失效，
这一屏当场现形。同一个毛病同一天在顶栏那条判据上更贵一些
（一次真实的 390 溢出被判绿了整整一批）。

## 本卡改了什么

只把声明改成**今天的实况**：`not_found` 那一态真的画出来了、且有样式
（`[data-workbench-state]` + `.workbench__error`）。
NEVER 留着 `[data-not-provided]` 与 `.workbench` / `.workbench__hint`——
它们此刻不渲染，尺子会拿一个不存在的元素判红，
而红的是**声明过期了**不是屏坏了。

## 本单要的那件事

**图真的画出来的样子，今天一次都没被量到过。**
`/workbenches/[id]` 的主路（有节点、有边、有 AI 栏）需要一个
库里真有的 id 才量得到。两种做法各有代价，请 owner 或下一张卡定：

| 做法 | 代价 |
|---|---|
| 声明里直接写 `wb-87be216d6b64` | 那一行依赖一条**活数据**；库被清一次，判据就红在「屏坏了」 |
| 取证前先种一张（像 `DEMO-TOPIC` 那样种夹具） | 要一条种子路径与撤销路径，且 `DEC-041` 的纪律是「种完要撤掉当初为空开的额度」 |

倾向第二种（与本仓既有做法同形），但那是一张卡，不是 `WB-01` 顺手能做的事。
