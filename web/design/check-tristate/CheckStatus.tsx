// DESIGN-13：后台检查三态（G19）。
//
// `unreported` 是「这项检查没跑或没回话」，它和「跑了、过了」是**两件相反的事**：
// 一个是不知道，一个是知道没问题。把不知道画成绿色，用户就会拿着一份「全绿」的界面
// 去做决定，而那些绿里有几格其实什么都没检查过。
//
// 所以三态在**三处**都分得开：class（看得见）、aria-label（读得出）、data-state（机器读）。
// 只靠颜色区分的话，色觉障碍用户与读屏用户拿到的就是两态。
//
// 未知状态**抛错**而不是当成 passed：多一个状态进来时，宁可在开发期炸掉，
// 也不要在界面上多一格看起来没问题的绿。
//
// 汇总同理：`all_passed` 只有在**每一项都 passed** 时才为真。有 unreported 就不是全过——
// 那是不知道；空清单也不是全过——一项都没有时说「通过」没有任何依据。

import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

export type CheckState = "passed" | "failed" | "unreported";

export const CHECK_STATES: readonly CheckState[] = ["passed", "failed", "unreported"];

const CLASS_OF: Record<CheckState, string> = {
  passed: "check-status check-status--passed",
  failed: "check-status check-status--failed",
  unreported: "check-status check-status--unreported",
};

const LABEL_KEY: Record<CheckState, string> = {
  passed: "design.check.passed",
  failed: "design.check.failed",
  unreported: "design.check.unreported",
};

export function CheckStatus({
  name,
  state,
}: {
  name: string;
  state: CheckState;
}): JSX.Element {
  if (!CHECK_STATES.includes(state)) {
    // 宁可在开发期炸掉，也不要在界面上多一格看起来没问题的绿
    throw new Error(`unknown check state: ${state}`);
  }
  const label = t(LABEL_KEY[state], { name });
  return (
    <span
      data-testid="check-status"
      data-check={name}
      data-state={state}
      className={CLASS_OF[state]}
      role="status"
      aria-label={label}
    >
      {label}
    </span>
  );
}

export function CheckSummary({
  checks,
}: {
  checks: { name: string; state: CheckState }[];
}): JSX.Element {
  const count = (state: CheckState) => checks.filter((c) => c.state === state).length;
  const passed = count("passed");
  const allPassed = checks.length > 0 && passed === checks.length;

  return (
    <div
      data-testid="check-summary"
      data-passed={passed}
      data-failed={count("failed")}
      data-unreported={count("unreported")}
      data-all-passed={String(allPassed)}
    >
      {checks.map((check) => (
        <CheckStatus key={check.name} name={check.name} state={check.state} />
      ))}
    </div>
  );
}
