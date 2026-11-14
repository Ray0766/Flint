# `design_generate` 有消费者、没入口 —— 提交那条端点不存在

**状态** closed @2026-08-08 · `ENTRY-01`（v0.4.1 第 6 批）

> 发现者：worker，v0.4.1 第 5 批 `DESIGN-02`（工作台②：那一屏是空壳）。

## 现象

`DESIGN-01` 刚把 `design_generate` 的**消费者**接上（`flint/jobs/design_generate.py`，
进了分派表、从 `UnwiredKindReason` 移出）。但**没有任何端点能把这类作业塞进队列**：

```
$ curl -s http://localhost:8000/openapi.json | python -c "…作业一族…"
['/jobs/{job_id}/verdict', '/jobs/{job_id}', '/jobs/{job_id}/events']
```

前端的提交器 `web/lib/jobClient.ts#submitJob` 打的是
`POST /projects/{id}/{kind}`——openapi 里没有 `design_generate` 那一条。
实测打过去回的是**框架那种没有 `code` 的 404**（`{"detail":"Not Found"}`，路由未挂）。

规格 `docs/前端功能说明-v2.md#2.17` 把生成那条记为
`POST /design`【未建·接口预留】——**至今仍然未建**。

## 屏上现在怎么说

按 `DEC-032`（未装配期间一律显示「接口未提供」，NEVER 显示空态／未启用／隐藏入口）：
输入区与生成键**照常在屏上**，按下去**真发请求**，然后把服务端的答复如实说出来
（虚线框 + 「接口未提供：生成入口还没挂」）。

**为什么照样发请求**：「能不能提交」的真相在服务端。前端自带一份「我知道它没有」的判断，
那份判断会与后端各自漂移——端点哪天挂上了，屏上仍然会显示「没有」。
发一次、按答复说话，是唯一不会说错的做法。

代价是控制台留下一条 404。**那条噪声登记在判据里而不是被掩盖**：
`tests/v041/test_design_workbench_ui.py::
test_the_only_console_noise_is_the_registered_missing_endpoint` 判等值——
多一条要停下来看，**少一条说明端点挂上了**，那时来删掉那一行并关掉本单。

## 三条路里另外两条是通的

| 端点 | 状态 |
|---|---|
| `GET /jobs/{id}/events` | 通。屏上用 `openJobStream` 续订，逐块拼由 `jobClient` 的 `designText` 做 |
| `GET /design/sessions/{job_id}/replay` | 通（`DESIGN-01` 刚把 `load_session` 接上，改前恒 404）。进屏先取回已产出的块 |
| `POST /projects/{id}/design_generate` | **不存在** |

所以「中断可续」那半是真的：带 `?job=` 进屏能拿回已经产出的文字，**NEVER 从头重跑**。
缺的只有「从零开一个新作业」。

## 需要 owner 的什么

1. **谁来挂那条端点**？它要动 `flint/api/`（提交 + 鉴权 + 幂等键），属后端面，
   不在本批 18 卡的触碰面内；
2. **挂在哪个路径**？规格写的是 `POST /design`，而既有作业族的惯例是
   `POST /projects/{id}/{kind}`（`submitJob` 就是按这个写的）。
   两者取一，**取定之后前端只改一个字符串**（`designSession.ts` 里那一处）。

## 绕行现状

`DESIGN-02` 三件按上面的姿态交付并 verified：输入区与流式区真做了、预览区本来就对。
生成那一步在端点挂上之前**开不出新作业**——如实记账，第 5 批完成态报告会点名。

---

## 结案（`ENTRY-01` · v0.4.1 第 6 批）

`POST /projects/{id}/design_generate` 已建，落在 `flint/api/analysis.py`。

**为什么落在 analysis.py 而不是 design.py**：`submitJob` 打的形状是
`POST /projects/{id}/{kind}`，而这条路径族（作业提交 + `/jobs/*` 快照与 SSE）
本来就归 analysis.py。挂到 design.py 会让**同一族路径分在两个模块**，
下一个人查「作业怎么提交的」要翻两处。

四种拒绝各说各的（`AUTH-03`），并有一条**阴性对照**断言它们
两两不同——没有那条，把三种都实现成 403 也能让其余判据各自绿。

**顺序是先认人、再找项目、最后判角色**：先查项目的话，一个没有身份的调用方
也能靠 404/200 的差别探出「哪些项目 id 存在」。

**404 由端点自己回**，NEVER 依赖装配处那个 `ProjectNotFound` 处理器：
那个只在挂载之后生效，子应用被单独起来时同一条路径会 500，
而一条「项目 id 打错了」以 500 收场，读起来是「服务器坏了」。
