// UIX-04：作业屏的第五态——**不让你看**。
//
// ## 这一条治的病：403 之后屏上是一张**永远转下去的骨架**
//
// `useJobStream` 与 `jobClient` 里此前 grep `403|denied|forbidden` **零命中**：
// SSE 被拒之后 `status` 恒为 `null`，屏上落在加载态。
// **「在连」与「不让你连」长得一模一样**，而两者要用户做的事完全相反：
// 一个是继续等，一个是去要权限。
//
// 单子：`docs/blocked/JOB-SCREEN-HAS-NO-DENIED-STATE.md`（本卡关闭）。
// 那张单同时纠正了第 5 批完成态报告里写错的一句
// （「屏上也正确地显示无权查看」——当时并没有）。
//
// ## 与断线件**刻意不共用**
//
// `SseDisconnectNotice` 说的是「正在重连，下面的内容可能不是最新的」——
// 那是**可恢复态**。而 403 是终局的：**重连一万次也还是 403**。
// 共用一句话的话，屏上会劝一个无权的用户「稍后重试」，
// 而重试永远不会成功——**那是一句假话，比不说更坏**。
//
// 所以本件里 NEVER 出现「重试」二字，判据钉着这一条。
//
// ## 401 与 403 是两句话（`AUTH-03` 口径）
//
// - 401「你是谁」→ 去登录；
// - 403「你能干什么」→ 这条作业不是你发起的，去找发起人要权限。
//
// 并成一句「无权访问」的话，用户不知道下一步该做什么——
// 而下一步不同，正是 `AUTH-03` 把两种 401 也分开的理由。
//
// ## 它是 `role="alert"` 而不是 `status`
//
// 断线是「情况有变，你可以继续看」（`status` / `polite`）；
// 无权是「你看不到任何东西」——那是一次**需要立刻知道**的终局，
// 读屏软件该打断当前朗读。

import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

export function JobDeniedNotice({
  reason,
}: {
  /** `denied` = 403（去要权限）；`unauthenticated` = 401（去登录）。 */
  reason: "denied" | "unauthenticated";
}): JSX.Element {
  // 两支**各把 key 写全**，NEVER 用一个变量前缀去拼 key。
  // 第一版就是拼的，`tools/i18n_key_defined.mjs` 当场报「引用了却没有定义的 key」——
  // 它解不开一个运行时才成形的字符串。
  //
  // （这段注释里**不写出那种拼法的字面形状**：那把扫描器连注释一起扫，
  //   写出来就等于在注释里又引用了一次一个不存在的 key。）
  //
  // 而那条报错指出的是一个**真问题**：拼出来的 key **grep 不到**。
  // 「`job.denied.hint` 这条文案被谁用了」从此答不出来，
  // 而下一个人删词条时看到的是「没有引用」。
  const copy =
    reason === "denied"
      ? { title: t("job.denied.title"), hint: t("job.denied.hint") }
      : {
          title: t("job.unauthenticated.title"),
          hint: t("job.unauthenticated.hint"),
        };
  return (
    <div
      className="state state--denied"
      data-screen-state={reason}
      data-job-denied={reason}
      role="alert"
    >
      <p className="state__title">{copy.title}</p>
      <p className="state__hint">{copy.hint}</p>
    </div>
  );
}
