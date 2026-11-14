# 选主题落不到 `chosen_topic_id` —— 只有读端点，没有写端点

**状态** closed @2026-08-08 · `ENTRY-02`（v0.4.1 第 6 批）

> 发现者：worker，v0.4.1 第 5 批 `CHAIN-03`。

## 现象

卡面 acceptance③：**选主题动作落到 `chosen_topic_id`，NEVER 前端自行记一份。**

openapi 里 topic 一族只有三条，**全是 GET**：

```
/topics/{topic_id}            ['get']
/projects/{project_id}/topics ['get']
/plaza/topics                 ['get']
```

`GET /projects/{id}/topics` 回的 `chosen_topic_id` 是**读**的那一半；
**写**的那一半没有任何端点。

## 本卡怎么交付的

选中态**恒由后端回的 `chosen_topic_id` 决定**，屏上照它高亮。
「选它」那个键仍在（`TopicListView` 早就有 `onSelectTopic`），
但列表屏**不传处理器**——按下去不会有任何本地状态改变。

**NEVER 前端自己记一份**：记了的话，刷新一次就没了，而用户以为自己已经选过，
并会在后面的分析里以为用的是他选的那条。

## 需要 owner 的什么

挂一条写端点（`PUT /projects/{id}/chosen-topic` 或 `POST /projects/{id}/topics/{tid}/choose`，
路径由 owner 定）。它要动 `flint/api/`，**不在本批 18 卡的触碰面内**。

端点挂上之后，本屏改动是**接一个处理器**（把 topic_id 发出去、再按回来的
`chosen_topic_id` 渲染），卡面与样式一行都不用动。

---

## 结案（`ENTRY-02` · v0.4.1 第 6 批）

`POST /projects/{id}/chosen-topic` 已建，落在**新模块** `flint/api/topics.py`。

**为什么不塞进 `views.py`**：那份文件的第一句是「既有模型上的只读端点」。
往里加一个写，等于让那句话从此不成立——而下一个人读到它时会信它。

- 越界校验与 change_log 追加**转调** `flint/topic/project.py#choose_topic`，端点一行不重写；
- **幂等在端点这一侧**：同一主题重复选不留第二条记录（那会让变更历史看起来像
  用户改了两次主意）；**换**主题时第二条必须留下，有阴性对照钉着——
  把幂等实现成「永远不追加」会把「改主意」从历史里抹掉；
- 四种拒绝各说各的（`AUTH-03`），另有阴性对照断言四者两两不同；
- 屏上那个「选它」按钮接上了，且**选中态仍恒取后端的值**——
  前端 NEVER 自己记一份（本单原本担心的正是这一条）。

### 顺出来的两件事

1. `PgProjectStore.save` 原先是**纯 INSERT**，只能建不能更——
   唯一的调用方（combo）永远新建，所以那个缺口一直没被执行到，
   本卡第二次 save 当场 500。已改成 upsert（`created_at` 不在更新列里）；
2. `useScreenData` **没有 refetch 句柄**，写完之后只能整屏重读。
   见 `docs/blocked/SCREEN-DATA-HOOK-HAS-NO-REFETCH.md`。
