// DESIGN-24：无障碍基线（G31）。
//
// ## 全键盘可达
//
// 一个只能用鼠标点到的按钮，对键盘用户就是**不存在**——他不会觉得「这里有个功能
// 我够不着」，他会觉得这个产品没有这个功能。所以判据是：每一个可交互点都能被 Tab 走到，
// 且不靠 `tabIndex` 正数去插队（正数会把整页 Tab 顺序打乱，其它元素反而被挤到后面）。
//
// ## focus-visible 而不是 outline: none
//
// 去掉焦点框会让键盘用户在页面上**看不见自己在哪**。`:focus-visible` 的意义正是
// 「鼠标点击不显框、键盘走到才显」——两边都照顾到；直接 `outline: none` 是把
// 键盘那半边砍掉。
//
// ## prefers-reduced-motion 下动效时长归零
//
// 这不是「减弱一点」：对前庭功能敏感的用户，一次滑入动效可能引发眩晕。
// 系统设置里那个开关是他明确表达过的需求，所以时长**归零**而不是「放慢」。

export type MotionPreference = "no-preference" | "reduce";

/** 动效时长（毫秒）。reduce 下恒为 0。 */
export function motionDurationMs(
  base: number,
  preference: MotionPreference,
): number {
  if (base < 0) throw new Error("motion duration must not be negative");
  return preference === "reduce" ? 0 : base;
}

/** 过渡样式：reduce 下连 transition 属性都不下发（0ms 仍会触发一次重排回调）。 */
export function motionStyle(
  base: number,
  preference: MotionPreference,
): { transitionDuration?: string } {
  return preference === "reduce" ? {} : { transitionDuration: `${base}ms` };
}

export type FocusableSpec = {
  /** 元素类型，用于判断是否天生可聚焦 */
  tag: string;
  tabIndex?: number;
  disabled?: boolean;
  ariaHidden?: boolean;
};

const NATURALLY_FOCUSABLE = new Set([
  "a", "button", "input", "select", "textarea", "summary", "iframe",
]);

/** 这个元素能不能被 Tab 走到。 */
export function isKeyboardReachable(spec: FocusableSpec): boolean {
  if (spec.ariaHidden === true) return false;         // 对读屏隐藏的东西不该抢焦点
  if (spec.disabled === true) return false;
  if (spec.tabIndex !== undefined) return spec.tabIndex >= 0;
  return NATURALLY_FOCUSABLE.has(spec.tag.toLowerCase());
}

export type A11yIssue = { index: number; reason: string };

// 审一组交互点：返回**说得出原因**的问题清单。
//
// 只回一个 true/false 的话，调用方只知道「有问题」，不知道是哪一个、为什么——
// 而无障碍问题恰恰是最需要「照着改」的那类。
//
// （行注释而非 JSDoc：扫描器对跨行块注释的已知假阳性，见 DEC-013 / 卡 I18N-09。）
export function auditInteractive(specs: FocusableSpec[]): A11yIssue[] {
  const issues: A11yIssue[] = [];
  specs.forEach((spec, index) => {
    if (spec.tabIndex !== undefined && spec.tabIndex > 0) {
      issues.push({
        index,
        reason: "positive tabIndex reorders the whole page; use DOM order instead",
      });
      return;
    }
    if (!isKeyboardReachable(spec) && spec.disabled !== true && spec.ariaHidden !== true) {
      issues.push({
        index,
        reason: `<${spec.tag}> is not reachable by keyboard; make it a button or give tabIndex=0`,
      });
    }
  });
  return issues;
}

/** 焦点样式：NEVER 用 outline:none 把键盘那半边砍掉。 */
export const FOCUS_VISIBLE_STYLE = {
  outline: "2px solid var(--focus-ring)",
  outlineOffset: "2px",
} as const;
