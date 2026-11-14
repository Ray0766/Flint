# VERDICT-CONSTRAINTS-CHECKED-TYPE · `Verdict.constraints_checked` 前端标成了 boolean，后端是对象

**状态** closed · 2026-08-05 · `TYPE-03`

> **已关闭 · 2026-08-05 · `TYPE-03`**
>
> `web/lib/viewsClient.ts` 新建 `ConstraintsChecked` 接口，字段**从
> `flint/gate/engine.py` 的构造处抽取**（不是手抄）：`order` ·
> `demoted_by_alignment` · `rule_a`（3 子字段）· `rule_b`（5）· `rule_c`（3）·
> `gap_count`。判据判**等值**——前端声明的顶层字段 == 后端放进去的顶层键。
>
> **改类型的那一刻当场抓到一处**：`web/components/views/views.test.tsx` 的夹具
> 写着 `constraints_checked: true`。**夹具照着错类型写，两边一起错**，
> 所以此前谁都看不出来。已按真形状改。
>
> **本单点名的那个危险点写成了会跑的判据**：
> `tests/v041/test_verdict_constraints_type.py` 拿**真 `tsc`** 编译一段
> 「把对象当 boolean 用」的代码，断言**编译不过**；再编译一段正确写法，
> 断言**通过**。两条都跑，才分得清「拦住了」和「见谁都拦」。
>
> `GateView` **仍然不渲染**这个字段（本卡只改类型）。另有一条判据盯着它：
> 哪天有人开始渲染，那条会红——**那正是该回头确认「面板是按六项依据画的」的时刻**。
>
> 以下为关闭前的原文，一字未改。

---

**发现者** worker / UI-02 挂 Gate 屏时 · **发现时间** 2026-08-04
**危害** 低（当前无人渲染它）→ 一旦有人渲染就变**中**：会在屏上显示 `true` 而不是判定依据
**改动面** `web/lib/viewsClient.ts` 一处类型 + 渲染它的组件（现在没有）

## 实测到的事

`web/lib/viewsClient.ts#Verdict`：

```ts
constraints_checked: boolean;
```

而后端 `GET /jobs/{job_id}/verdict` 回的是 `snapshots['snap-{job}-verdict']` 的
原样 payload，那里面 `constraints_checked` 是**对象**——按蓝本
`design_handoff_flint_web/README.md` 的「已知缺陷提醒」一节原话，字段有
`order` / `demoted_by_alignment` / `rule_a` / `rule_b` / `rule_c` / `gap_count`。

蓝本那份 README 自己就写着：「`web/lib/viewsClient.ts` 将 verdict 的
`constraints_checked` 误标为 boolean —— 后端实为对象……**挂 Gate 视图时修正**
（P8 已按对象渲染成可展开判定依据）」。

## 为什么现在还没出事

`web/components/views/GateView.tsx` **不渲染这个字段**（它只渲染 verdict / 引用 /
理由 / 竞品 / gaps）。UI-02 的 Gate 屏直接用了那个既有组件，所以这条错类型
一次都没被执行到。

**危险在于它看起来是对的**：下一个人要把「判定依据」做成可展开面板时，
会照着类型写 `{verdict.constraints_checked ? …}`——一个非空对象恒为真，
于是屏上出现一个永远展开、内容为 `true` 的面板，而真正的六项依据一项都不显示。

## 为什么 UI-02 没有顺手改

`web/lib/viewsClient.ts` 不在 UI-02 的 outputs 里（卡上是 `web/app/` +
`tests/v041/test_ui_mainchain.py`）。工单 §六.1：改动面大于卡上 outputs → 停下走
`docs/blocked/`。本卡绕得开（Gate 屏不渲染它），所以绕行 + 立单。

## 要 owner 提供什么

一个判断：这条**跟着哪张卡修**。两个候选——

1. **随「判定依据可展开面板」那张 UI 卡**（蓝本 P8 的完整形态）：那时必须改，
   顺手改最省；
2. **单开一张类型对齐卡**：把 `constraints_checked` 改成对象类型 + 补一条
   「前端类型与后端 payload 逐字对齐」的判据。第 2 条更彻底——
   这个字段大概率不是唯一一处对不上的，但只查一处等于没查。

## 绕行现状

UI-02 的 Gate 屏正常工作，判定四分类、引用、理由、竞品、gaps 全部据实呈现。
`constraints_checked` 既不读也不渲染。
