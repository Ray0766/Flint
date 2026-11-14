# `SourceColumns` 把话还给了说话的人，**却没在屏上写出他是谁**（**已关闭** @2026-08-09）

**状态** closed · 2026-08-09 · `FIX-17`

> **owner 选甲**：每条陈述前加一行**可见**的来源名。
>
> 改了三处：`SourceColumns.tsx` 多渲染一格 `source-statement-who`；
> 新增 `sourceName.ts`（四个源 → 词条 key 的**明写**映射，认不出的 id 原样显示）；
> `web/messages/{zh,en}.json` 各加 4 个 key。
>
> **判 `data-source-id` 的既有 10 条判据一条没动**——它防的是混列，那是另一件事。
> 新判据取**渲染后的可见文本**（`web/components/source-columns/attribution.test.tsx`
> 6 条 + `tests/v041/test_source_columns_attribution.py` 9 条）。
>
> 其中一条直接钉住本单的现象：`ghtrend` 与 `gtrends` **同属未归区**（地区那一列
> 在这里帮不上任何忙）时，只看屏上的字也分得出谁说的。改前那两句都读不到。
>
> 「四个源」的真相取自 `flint/sources/*.py` 的 `source_id`，**不在前端抄一份**——
> 新增一个源而前端没跟上，判据当场红。
>
> 以下为关闭前的原文，一字未改。

---

> 发现者：worker，v0.4.1 第 7 批 `REGION-12`（接上原文词面之后**看了一眼屏**）。
> 改法在 `web/components/source-columns/SourceColumns.tsx`——**v0.4 已 verified**
> （`HOTSPOT-07`，2026-08-02）。按 `worker.md` §9.2 / `DEC-021`
> 「需要改 v0.4 已 verified 的文件时，停下报 owner」立单，NEVER 自行动手。

## 一、屏上实况

`REGION-12` 把词面接上之后，那条两源分歧的簇（`c-20260629-108`）在广场上长这样：

```
brain-computer interface          ← 卡面主行：**我们**给这个热点起的名字
2026-06-29   热度 100

未归区                             ← 列标题 = 地区
  ○ bci
  ○ 脑机接口
```

DOM 里两条各自带着 `data-source-id="ghtrend"` / `data-source-id="gtrends"`，
**而屏上一个字都没有**。`SourceColumns.tsx` 的渲染逐字如下：

```tsx
<li data-source-id={s.sourceId}>
  <span data-testid="source-statement-text">{s.text}</span>
</li>
```

来源 id 只进了属性，没进可见文本。

## 二、为什么这不是小事

这个组件的**全部理由**写在它自己的文件头：

> 读者失去了「谁说的」这个唯一能判断可信度的东西。

屏上现在正是这个状态：两条说法并排，**读者判不出哪句是 GitHub 说的、哪句是
Google Trends 说的**。`PRINCIPLES#B4` 说「把话还给说话的人」，
而话还回去了、人没写上。

**地区那一列不够顶这件事。** 列标题是地区（`CN` / `未归区`），
它只在两个源恰好分属两个区时才顺带区分了它们。今天库里的实况是
`global = 103 · CN = 89 · NULL = 1`——绝大多数簇的源要么同区、要么无区，
**同一列里两条陈述，谁说的就完全看不出来**。

而多源恰恰是这个组件唯一会被用到的场合：本机 demo 库 106 条簇里
**只有 1 条是多源的**，就是上面这一条。它演示的正是这个缺陷。

## 三、为什么没有判据抓到

`HOTSPOT-07` 的判据（`SourceColumns.test.tsx`，10 条）用
`within(column).getByTestId(...)` 逐列查 `data-source-id`——
它判的是「来源 id **在 DOM 里**且没混列」，那条判据是对的、也该留着。

但「在 DOM 里」与「在屏上」是两件事。**读屏软件念得出这一条**（属性不进无障碍树时也念不出），
而肉眼看不见。本仓一路在守的同一条：`data-*` 是给取证用的，产品语言是给人看的。

## 四、四选一（给 owner）

| 选项 | 做什么 | 代价 | 我的看法 |
|---|---|---|---|
| **甲** | 每条陈述前加一行可见的来源名（`t("source.name." + sourceId)`，映射表已在 `enumLabel` 一族） | 改 4 行冻结组件 + 4 个源的文案 key | **推荐**。它把这个组件自己写下的理由补完 |
| 乙 | 只加 `aria-label`，屏上不变 | 改 1 行 | 读屏用户拿到了，看屏的人还是拿不到——**而缺陷是给看屏的人的** |
| 丙 | 列标题从「地区」改成「地区 · 源」 | 改列分组语义 | **不建议**：那会推翻 `HOTSPOT-07` 的分列口径（按地区分列是 `B4` 的原话），改动面比甲大得多 |
| 丁 | 不改 | 0 | 那这个组件在最常见的情形下**不做它声称在做的事** |

选甲的话，另需一条判据：**屏上可见文本里能读到来源**——
判 `data-source-id` 的那条留着不动（它防的是混列），新加一条判可见文本。

## 五、本卡（`REGION-12`）绕行现状

词面已经接上、逐字、缺项如实标注，`by_source_text` 与 `ClusterSourceLines`
都在位。**唯一没解决的就是这一条：屏上看不出谁说的。**
它不阻塞 `REGION-12` 的任何一条 acceptance——那四条问的是词面对不对、
有没有被分数顶替、缺项标没标、合成句有没有。

`PLAZA-02` 因此照常关闭；本单是**新发现的、另一件事**。
