"use client";

import type { JSX } from "react";
import { t } from "../../../lib/i18n/t";
import { use } from "react";
import { useJobStream } from "../../../lib/useJobStream";
import { API_BASE } from "../../../lib/apiBase";
import { EmptyState } from "../../../components/shell/EmptyState";
import { ErrorState } from "../../../components/shell/ErrorState";
import { JobDeniedNotice } from "../../../components/shell/JobDeniedNotice";
import { LoadingSkeleton } from "../../../components/shell/LoadingSkeleton";
import { Screen } from "../../../components/shell/Screen";
import { SseDisconnectNotice } from "../../../components/shell/SseDisconnectNotice";

// L1 渐进交付页（客户端）：订阅 Job SSE，实时显示状态/步骤/已到达 block 数/失败。
// 逻辑在 useJobStream + jobClient（已测）；本页为薄呈现层。全 block 内容的逐块
// 实时渲染需 job→deliverable 关联 + 单块内容取数（后续卡），此处先呈现进度。
//
// UI-01 重做的是样式面：屏头 + 数据行走 mono/tabular-nums（蓝本 Design Tokens 一节
// 原话「一切带出处数值/id/时间戳」走 mono），失败原因走 --rust。
// **取证属性一个没动**：`data-job-id` / `data-job-status` / `data-arrived-count` /
// `data-job-failed` / `data-job-steps` 是既有断言面（蓝本 README 原话「保留其零计算
// 注释与 data-* 断言属性」）——改样式 NEVER 顺手改断言面。
//
// **NEVER 上进度条**：蓝本原话「无可靠度分值 → 全站无进度条/百分比/星级/雷达图」。
// 已到达 block 数是个真数字，除以一个不存在的总数就成了假进度。
//
// ## 本屏现在是**五态**（UIX-04 加了第五个）
//
// | 态 | 判据 | 说的是 |
// |---|---|---|
// | 无权 | `access !== "unknown"` | 401 去登录 / 403 去要权限。**排在最前**，见下 |
// | 加载骨架 | `status === null` | 还没收到第一个事件（我们在连） |
// | 失败 | `failedReason` | 后端明确发来的作业失败（**不是**断线） |
// | 空 | 收到事件但零 block | 在跑，还没产出 |
// | 就绪 | 其余 | — |
export default function JobPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): JSX.Element {
  const { id } = use(params);
  const s = useJobStream(id, { baseUrl: API_BASE });
  // UIX-04：**第五态，而且它排在骨架之前**。
  //
  // 后端对这条作业回 403（或 401）时，`status` 恒为 `null`——落到下面那个加载分支，
  // 于是屏上是一张**永远转下去的骨架**：「在连」与「不让你连」长得一模一样，
  // 而两者要用户做的事完全相反（一个继续等，一个去要权限）。
  //
  // **排在骨架之前**是必需的：骨架那条的条件是 `status === null`，
  // 无权时它同样成立。排在后面的分支永远命中不到。
  //
  // 无权时**不再画骨架**：两个一起出现，用户读到的还是「等一等」。
  //
  // 条件是**正向枚举那两个态**，NEVER 写成 `!== "unknown"`：
  // 后者会把「这个字段不存在」（旧的调用方、桩、老录制）也当成拒绝——
  // 而那正是 `probeJobAccess` 自己拒绝去做的事（探不出来就是 `unknown`，
  // NEVER 猜成 denied）。第一版就是这么写的，当场把两条既有判据打红：
  // 桩里没有 `access`，于是那一屏的五个取证属性整片消失。
  if (s.access === "denied" || s.access === "unauthenticated") {
    return (
      <Screen title={t("job.screen.title")} meta={t("job.screen.meta")}>
        <div data-job-id={id}>
          <JobDeniedNotice reason={s.access} />
        </div>
      </Screen>
    );
  }
  // UIX-01：三态各就各位。**这一屏的三态是这样对应的**：
  //
  // - `status === null` = **还没收到第一个事件**（SSE 正在连）→ 加载态。
  //   此前这里画的是一句 `t("job.status.connecting")` 塞进状态栏——
  //   看起来像「作业的状态叫 connecting」，而那是**我们**在连，不是作业在连。
  // - `failedReason` = 后端明确发来的**作业失败** → 错误态。
  //   注意它**不是断线**：断线那一态本仓还没有，
  //   见 docs/blocked/SSE-DISCONNECT-IS-SILENT.md（UIX-02 处置）。
  // - 收到了事件、但一个 block 都还没到 → 空态，且要说清「在跑，还没产出」。
  if (s.status === null) {
    return (
      <Screen title={t("job.screen.title")} meta={t("job.screen.meta")}>
        <LoadingSkeleton rows={3} label={t("job.status.connecting")} />
      </Screen>
    );
  }
  return (
    <Screen title={t("job.screen.title")} meta={t("job.screen.meta")}>
      {/* UIX-02：断线时说出来，NEVER 静静停在旧数据上。
          放在最上面、且**不藏下面的内容**——旧内容仍然是真的，只是可能过时。
          `data-job-connection` 是新的断言面（原有五个属性一个没动）。 */}
      <div data-job-connection={s.connection}>
        {s.connection === "disconnected" ? <SseDisconnectNotice /> : null}
      </div>
      <div data-job-id={id}>
        <div className="data-row">
          <span className="data-row__label">{t("job.field.status")}</span>
          <span className="data-row__value" data-job-status>
            {s.status ?? t("job.status.connecting")}
          </span>
        </div>
        <div className="data-row">
          <span className="data-row__label">{t("job.field.arrived")}</span>
          <span className="data-row__value" data-arrived-count>
            {s.arrivedBlockIds.length}
          </span>
        </div>
        {s.failedReason ? (
          // 后端给的理由**原样带出去**，NEVER 改写成一句通用的「失败」。
          // 既有断言面**逐字保留**：`data-job-failed` + `job-failed` 类 +
          // 失败原因作为该元素的文本。`ErrorState` 套在里面提供视觉与
          // `role="alert"`，但**不许把断言面挤掉**——
          // 改样式 NEVER 顺手改断言面（本卡实测被那条判据当场拦下）。
          <>
            <p className="job-failed" data-job-failed>
              {s.failedReason}
            </p>
            {/* 通用件另起一块：它带 `role="alert"`（读屏软件立刻念）。
                两块并存不是重复——上面那块是**断言面**，这块是**给人看的**。
                合成一块的话，要么丢断言面，要么丢无障碍语义。 */}
            <ErrorState title={t("job.failed.title")} detail={s.failedReason} />
          </>
        ) : null}
        {s.steps.length === 0 && !s.failedReason ? (
          // **查过了**（事件已到），只是还没有步骤——这才是空态。
          <EmptyState title={t("job.steps.empty")} hint={t("job.steps.empty_hint")} />
        ) : null}
        <ol className="data-list" data-job-steps>
          {s.steps.map((step, i) => (
            <li className="data-row" key={i}>
              <span className="data-row__label">{step.step_name}</span>
              <span className="data-row__value">{step.phase}</span>
            </li>
          ))}
        </ol>
        {/* NAV-05：跑完了才给通往判定的入口。
            Gate① 的判定按 **job** 键落盘，所以这一屏手上的 id 就是那把钥匙
            （`/gate/{jobId}`，`DEC-012` 的形态）。

            **NEVER 一进来就给**：作业还在跑的时候点过去，判定屏会如实说
            「未判定」——那句话没错，可它读起来像「这次没判出结果」，
            而真相是「还没跑到」。两件事该说的话完全不同。

            失败那一路也不给：失败的作业不会有判定，给了就是把人送去看一句
            与失败无关的「未判定」。 */}
        {s.status === "done" ? (
          <p className="data-row" data-gate-entry>
            <span className="data-row__label">{t("job.gate_entry.label")}</span>
            <a className="data-row__value" data-gate-link href={`/gate/${id}`}>
              {t("job.gate_entry.open")}
            </a>
          </p>
        ) : null}
      </div>
    </Screen>
  );
}
