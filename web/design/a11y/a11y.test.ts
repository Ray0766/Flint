// DESIGN-24 验收：无障碍（全键盘可达 / focus-visible / reduced-motion 归零）。
//
// acceptance：**Tab 可达全交互点；reduced-motion 下动效时长为 0**。
//
// 一个只能用鼠标点到的按钮，对键盘用户就是**不存在**——他不会觉得「这里有个功能
// 我够不着」，他会觉得这个产品没有这个功能。
//
// reduced-motion 下归零也不是「减弱一点」：对前庭功能敏感的用户，一次滑入动效
// 可能引发眩晕。系统设置里那个开关是他明确表达过的需求。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { codeOnly } from "../../test-utils/source";
import {
  auditInteractive,
  FOCUS_VISIBLE_STYLE,
  isKeyboardReachable,
  motionDurationMs,
  motionStyle,
} from "./a11y";

const CODE = codeOnly(readFileSync(join(__dirname, "a11y.ts"), "utf8"));

describe("reduced-motion", () => {
  it("reduce 下时长归零，而不是放慢", () => {
    expect(motionDurationMs(240, "reduce")).toBe(0);
    expect(motionDurationMs(240, "no-preference")).toBe(240);
  });

  it("reduce 下连 transition 属性都不下发", () => {
    expect(motionStyle(240, "reduce")).toEqual({});
    expect(motionStyle(240, "no-preference")).toEqual({ transitionDuration: "240ms" });
  });

  it("负时长直接拒：那是接线错了", () => {
    expect(() => motionDurationMs(-1, "no-preference")).toThrow();
  });
});

describe("键盘可达", () => {
  it.each([["button"], ["a"], ["input"], ["select"], ["textarea"], ["summary"]])(
    "%s 天生可聚焦",
    (tag) => {
      expect(isKeyboardReachable({ tag })).toBe(true);
    },
  );

  it("div/span 默认够不着：要么换成 button，要么给 tabIndex=0", () => {
    expect(isKeyboardReachable({ tag: "div" })).toBe(false);
    expect(isKeyboardReachable({ tag: "div", tabIndex: 0 })).toBe(true);
  });

  it("tabIndex=-1 不在 Tab 序里：那是给程序聚焦用的", () => {
    expect(isKeyboardReachable({ tag: "div", tabIndex: -1 })).toBe(false);
  });

  it("disabled 与 aria-hidden 不抢焦点", () => {
    expect(isKeyboardReachable({ tag: "button", disabled: true })).toBe(false);
    expect(isKeyboardReachable({ tag: "button", ariaHidden: true })).toBe(false);
  });
});

describe("auditInteractive（说得出原因的清单）", () => {
  it("一屏交互点全可达时清单为空（阴性对照）", () => {
    expect(
      auditInteractive([{ tag: "button" }, { tag: "a" }, { tag: "div", tabIndex: 0 }]),
    ).toEqual([]);
  });

  it("够不着的元素报出来，并说清怎么改", () => {
    const issues = auditInteractive([{ tag: "button" }, { tag: "div" }]);

    expect(issues).toHaveLength(1);
    expect(issues[0].index).toBe(1);
    expect(issues[0].reason).toContain("tabIndex=0");
  });

  it("正数 tabIndex 也算问题：它会把整页 Tab 顺序打乱", () => {
    const issues = auditInteractive([{ tag: "button", tabIndex: 3 }]);

    expect(issues).toHaveLength(1);
    expect(issues[0].reason).toContain("reorders");
  });

  it("disabled 与 aria-hidden 不算问题：它们本来就不该被 Tab 到", () => {
    expect(
      auditInteractive([
        { tag: "button", disabled: true },
        { tag: "div", ariaHidden: true },
      ]),
    ).toEqual([]);
  });

  it("清单带下标：改的人要知道是第几个", () => {
    const issues = auditInteractive([{ tag: "div" }, { tag: "button" }, { tag: "span" }]);

    expect(issues.map((i) => i.index)).toEqual([0, 2]);
  });
});

describe("焦点可见", () => {
  it("焦点样式用 outline + 偏移，颜色走 token", () => {
    expect(FOCUS_VISIBLE_STYLE.outline).toContain("var(--focus-ring)");
    expect(FOCUS_VISIBLE_STYLE.outlineOffset).toBe("2px");
  });

  it("源码里没有 outline: none：那是把键盘那半边砍掉", () => {
    expect(CODE).not.toMatch(/outline:\s*["']?none/);
  });

  it("源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
