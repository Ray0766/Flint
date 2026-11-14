// 状态标记：**NEVER 只靠颜色区分**（`A4` 规则的可量对象）。
//
// ## 为什么这条不是「无障碍加分项」
//
// 只靠颜色的状态标记，在四种很常见的情况下**完全失效**：
//
// 1. **灰度打印**——报告被打出来交给评审，红绿两点变成一样的灰点；
// 2. **色觉差异**——红绿型是最常见的一种，而「成功/失败」偏偏最爱用红绿；
// 3. **强制暗色 / 高对比模式**——系统会覆写颜色；
// 4. **截图转黑白**（本仓的 `.ui-probe` 取证里就有）。
//
// 所以每个状态**必带一个非颜色载体**：这里用 `glyph`（形状字符）+ 文字。
// 颜色仍然给，但它是**第三条线索**，不是唯一那条。
//
// ## 文字是从后端来的，形状是查表来的
//
// `state` 由后端给（`data-row-state` 那一族），前端 NEVER 自己判。
// 认不出的状态**照样显示那个字符串**并给一个中性形状——
// NEVER 悄悄不画：不画的话，屏上看起来就像「这一行没有状态」，
// 而真相是「有状态，但我们没见过这个值」。

import type { JSX } from "react";

/** 状态 → 非颜色载体。**形状是这张表的主角**，色调只是陪衬。 */
const GLYPHS: Record<string, { glyph: string; tone: string }> = {
  // 完成：实心圆点 + 对勾形。
  done: { glyph: "●", tone: "ok" },
  succeeded: { glyph: "●", tone: "ok" },
  // 进行中：半环——与「完成」的实心点**形状不同**，不是同一个点换颜色。
  running: { glyph: "◐", tone: "busy" },
  queued: { glyph: "○", tone: "busy" },
  // 失败/阻塞：叉形。`--rust` 全站仅三处，这是其中一处（阻塞标）。
  failed: { glyph: "✕", tone: "rust" },
  blocked: { glyph: "✕", tone: "rust" },
};

/** 没见过的状态用它——**中性形状，不是「没有形状」**。 */
const UNKNOWN = { glyph: "◇", tone: "neutral" };

export function StatusMark({
  state,
  label,
}: {
  /** 后端给的状态字符串。前端 NEVER 自己判定，只负责显示。 */
  state: string;
  /** 屏上念出来的那个词。不给就显示 `state` 本身——NEVER 编一个。 */
  label?: string;
}): JSX.Element {
  const mark = GLYPHS[state] ?? UNKNOWN;
  return (
    <span
      className={`status-mark status-mark--${mark.tone}`}
      data-status-mark={state}
      // 形状与色调**分开**记：取证时能一眼看出「是不是只有颜色在变」。
      data-status-glyph={mark.glyph}
      data-status-tone={mark.tone}
    >
      {/* 形状：非颜色载体之一。灰度下它仍然分得出来。 */}
      <span className="status-mark__glyph" aria-hidden="true">
        {mark.glyph}
      </span>
      {/* 文字：非颜色载体之二，也是读屏软件唯一能念的那条。 */}
      <span className="status-mark__label">{label ?? state}</span>
    </span>
  );
}
