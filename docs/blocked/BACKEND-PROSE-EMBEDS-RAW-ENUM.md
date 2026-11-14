# 后端散文里嵌着枚举原值 —— 前端换不掉，也不该换

**状态** closed @2026-08-08 · `FIX-12`（v0.4.1 第 6 批）

> 发现者：worker，v0.4.1 第 5 批 `DS-03`（枚举原值换人类标签）。

## 现象（真栈取证原样输出）

`/gate/job-gate1-live-qwen` 屏上可见文字里有一句：

```
竞品扫描覆盖未达标（not_saturated）（search）
```

`not_saturated` 是 `flint/competitor/coverage.py::CoverageReason` 的原值。
拼这句话的是后端：

```python
# flint/gate/rule_d.py:44
missing_what=f"竞品扫描覆盖未达标（{coverage.reason}）",
```

## 为什么前端不该自己修

`GateView` 对 `missing_what` 的做法是**原样渲染**，那是对的——
`ErrorState` 那条既有纪律逐字适用：「后端自己的说明原样带出来，改写成一句通用的话，
等于把唯一有用的线索丢掉」。前端在这里做字符串替换有三重坏处：

1. 它要认得后端每一种拼法，而拼法随时会变；
2. 替换过的句子**看起来仍然是后端说的**，出错时没人找得到是谁改的；
3. 同一条 gap 在导出的报告（后端渲染）与屏上（前端渲染）会是两句话。

## 为什么 worker 不自己改后端

`flint/gate/rule_d.py` 属 **v0.4 已 verified 的实现**，`worker.md §9.2` 写死：
需要改这类文件时**停下报 owner**，NEVER 自行动手。
本批 18 张卡的触碰面是表现层，也不含 `flint/`。

## 建议的修法（请 owner 裁）

**`GapHint` 多带一个字段，把「原因码」与「给人看的话」分开**：

```python
missing_what="竞品扫描覆盖未达标"        # 给人看的话，不含原值
cause_code=coverage.reason               # 原值，前端拿它查标签表
```

前端已经备好了那张表（`web/lib/i18n/enumLabel.ts` 的 `coverage` 族，
五个成员与 `CoverageReason` 逐字对齐，中英标签齐备），拿到 `cause_code` 即通。
`GapHint` 加字段属冻结件面，**要走 owner 的变更通道**（CLAUDE.md S2-1）。

## 绕行现状

`tests/v041/test_enum_labels.py` 把这一条**逐字登记成例外**（`BACKEND_PROSE_EXCEPTIONS`），
并配一条反向判据 `test_the_registered_backend_prose_still_shows_up`：
**这句话哪天不在屏上了，判据会红并要求来删这一行**——
NEVER 留一条修好之后还赖着的豁免（那等于把尺子的一部分永久关掉，
而报告上仍写着「0 处原值」）。

---

## 结案（`FIX-12` · v0.4.1 第 6 批）

### 那句话改成了什么

```
改前  竞品扫描覆盖未达标（not_saturated）（search）
改后  竞品扫描覆盖未达标             ← missing_what（人话，零机器值）
      reason_code = "not_saturated"  ← 结构化那一半，前端按 DS-03 标签表说人话
      params      = {"pending_queries": [...]}
```

**原因码没被丢掉，它换了个位置。** 只把括号里那截删掉的话，屏上确实干净了，
而「为什么没达标」这个信息没了——那比印一个机器值更坏：
用户从此不知道该去补什么。

### `GapHint` 是冻结件，所以结构化的那一半加在序列化层

加字段是 `S2-1` 禁止的。`flint/gate/rule_d.py` 改回 `DerivedGap`
（冻结件那一份原样装在 `hint` 里，原因码与参数并排放），
`flint/jobs/gate1.py` 拼的那个 dict **不是冻结件**，两半在那里一起发出去。

**判定语义一字不动**：`decide()` 吃的仍是 `[d.hint for d in gaps]`，
判据逐条比对派生出的 `(cause, action)` 序列。

### 同一个毛病的第二处也修了

`flint/sources/degradation.py#card_gap_annotations` 的 docstring 逐字写着
「E6 row 1 **user-facing copy**」，而它拼的是 `f"今日缺 {源} 数据（{n.reason}）"`。
**拦得住新的却留着旧的，那条判据从第一天起就是绿的谎。**

### 留下来的那把尺子

`tests/v041/test_no_raw_enum_in_prose.py` 扫全 `flint/`：
**中文句子里 NEVER 插一个枚举字段**（`reason`/`cause`/`status`/`state`/`kind`/
`strength`/`alignment`/`verdict`）。

口径刻意窄，且**`raise` 里的不算**——这一条是开工后加的：
本仓的异常消息也写中文，而**异常是给我们自己看的**，
把出问题的那个值印出来正是它该做的事。所以「中文」不足以分开两者，
「是不是 `raise` 的实参」才是。

判据自带阴性对照：注入一条那种写法必须抓到；干净的写法与异常消息必须不报。
