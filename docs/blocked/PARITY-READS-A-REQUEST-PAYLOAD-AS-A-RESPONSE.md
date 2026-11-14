# 对账器把**请求 payload** 当成了响应形状

**状态** closed · 2026-08-10 · `COMBO-ECHO`（`PERSIST-04` 引入 · `ENTRY-05` 修掉主因 · `COMBO-ECHO` 收掉最后一处）

**开单人**：worker，第 9 批收尾时实测发现。**这一条是我引入的**，写清楚免得下一个人当成后端漂移。

## 现象

```
kind:     field_mismatch
subject:  /projects/{}/analysis
where:    flint/api/analysis.py
expected: ['topic_id']
actual:   ['keywords', 'locale', 'project_id']
note:     前端在 types.ts#AnalysisSubmitEcho 里为这条端点建了类型，
          但后端这几个字段没被声明（真漂移）
```

那句 `（真漂移）` **不对**。

## 根因

`tools/check_fe_be_parity.py#_handler_keys` 收的是**处理函数体里所有字面量 dict 的键**：

```python
def _handler_keys(handler, helpers):
    keys = list(_literal_dict_keys(handler))    # ← 函数体里**每一个**字面量 dict
    ...
```

而 `POST /projects/{id}/analysis` 的函数体里那个字面量 dict 是**提交给作业队列的
payload**，不是响应：

```python
job_id = await deps.runner.submit(
    kind="gate1_analysis",
    payload={"project_id": …, "keywords": …, "locale": …, "topic_id": …},   # ← 请求侧
    …)
return JSONResponse(AnalysisSubmitResponse(job_id=job_id).model_dump())      # ← 真响应
```

**真响应只有 `job_id` 一个字段。**

`PERSIST-04` 往那个 payload 里加了 `topic_id`（那是 cluster→判定关系表的
唯一数据来源，见 `docs/trace/PERSIST-04.md`），键集一变，
对账器挑接口的那一步就换了个匹配对象，于是报出这条 `field_mismatch`。

**改之前这条端点没报，不是因为它当时对得上，是因为键集恰好没匹配上任何接口。**

## 为什么不在本批顺手改

三条，第三条最硬：

1. 改对账器（让它只读 `return` 那一侧）**是改一把尺子**，
   而这把尺子今天守着 21 条 `backend_unused_by_frontend` 与 2 条 untyped——
   动它要重新确认那 23 条不受影响；
2. `tools/` 不在 `PERSIST-04` 的 outputs 里；
3. **「对账器三个空表」正是 `ENTRY-05` 的 acceptance②**，而那张卡今天被
   `PERSIST-02` 卡着。收口该在那里做，一次做完，而不是分两处各修一半。

## 建议的修法（留给 `ENTRY-05`）

让 `_handler_keys` 只收**返回值那一侧**的字面量 dict——
`JSONResponse({...})` / `return {...}` / `*_json(...)` 辅助，
而 `submit(payload={...})` 这种**入参 dict 不算**。

阴性对照现成：改完之后 `/projects/{}/analysis` 这条 `field_mismatch` 应当消失，
而其余 23 条一条都不该变。

## 绕行现状

这一条**保持红**。`PERSIST-04` 的功能本身不受影响
（`topic_id` 确实进了 payload，关系行确实写得下，14 条判据全绿）。

---

## 关闭（`COMBO-ECHO`）

本单记的两件事，**主因在第 9 批 `ENTRY-05` 就修掉了**（对账器只数
`return` 到得了的 dict，`payload=` 那类不再被当成响应）；
留着的是第二件：`/projects/combo` 的前端类型描述了一份不存在的形状。

`COMBO-ECHO` 收口。**选的是改前端，不是给后端补三个字段**——
补上就是让虚构变成事实；而且那三格本来也不该有：
`card_ids` 与 `hypothesis` 是调用方自己刚发出去的，回声一份只会让人去信回声
而不信自己的入参；`n` 从来就不是一个响应字段（它来自 `counter = {"n": 0}`）。

落地：`ComboSubmitEcho` → `ComboCreateResponse{project_id, topic_ids, degraded}`，
`AnalysisSubmitEcho` → `AnalysisSubmitResponse{job_id}`（同一处病的另一半）。
判据**拿真响应比对**（`model_dump()` 的键，就是端点交出去的那些），
NEVER 比两份人写的声明——两边一起写错时那种比法照样绿。
