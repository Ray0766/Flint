// DESIGN-22 验收：六条快捷键绑定生效且可在设置查看。
//
// acceptance：**⌘⏎/⌘Z/⌘\/⌘1/⌘2/⌘K 六绑定生效且可在设置查看**。
//
// 「可在设置查看」不是附赠：用户记不住六条键，他会去设置里看一眼再按。
// 如果那张表和实际注册的不是同一份，他照着看到的按，然后以为键盘坏了。
// 所以测试断的是**同一份表**，而不是「设置页有个列表」。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { codeOnly } from "../../test-utils/source";
import { SHORTCUTS, listShortcuts, matchShortcut } from "./shortcuts";

const CODE = codeOnly(readFileSync(join(__dirname, "shortcuts.ts"), "utf8"));

function ev(
  key: string,
  { meta = false, ctrl = false, inInput = false } = {},
) {
  return { key, metaKey: meta, ctrlKey: ctrl, inInput };
}

describe("绑定表", () => {
  it("恰是六条，id 与卡上一致", () => {
    expect(SHORTCUTS.map((s) => s.id)).toEqual([
      "send", "undo", "toggleAiPanel", "tabGraph", "tabTree", "commandPalette",
    ]);
  });

  it("设置页读的是同一份表（不是另抄一份）", () => {
    expect(listShortcuts()).toBe(SHORTCUTS);
  });

  it("每条都带展示文案 key：设置页要说得出这条键干什么", () => {
    for (const binding of SHORTCUTS) {
      expect(binding.labelKey).toMatch(/^design\.shortcut\./);
    }
  });
});

describe("matchShortcut（mac：⌘）", () => {
  it.each([
    ["enter", "send"],
    ["z", "undo"],
    ["\\", "toggleAiPanel"],
    ["1", "tabGraph"],
    ["2", "tabTree"],
    ["k", "commandPalette"],
  ])("⌘%s → %s", (key, id) => {
    expect(matchShortcut(ev(key, { meta: true }), "mac")).toBe(id);
  });

  it("不带修饰键不触发：单按 z 是在打字", () => {
    expect(matchShortcut(ev("z"), "mac")).toBeNull();
  });

  it("mac 上 Ctrl 不当 ⌘ 用：两键在 mac 上是不同的键", () => {
    expect(matchShortcut(ev("z", { ctrl: true }), "mac")).toBeNull();
  });
});

describe("matchShortcut（其它平台：Ctrl）", () => {
  it("Ctrl+Z 生效", () => {
    expect(matchShortcut(ev("z", { ctrl: true }), "other")).toBe("undo");
  });

  it("非 mac 上按 ⌘ 不触发（Windows 键不是修饰键）", () => {
    expect(matchShortcut(ev("z", { meta: true }), "other")).toBeNull();
  });
});

describe("输入框里的取舍", () => {
  it("⌘Z 在输入框里不抢：用户想撤的是刚打的字", () => {
    expect(matchShortcut(ev("z", { meta: true, inInput: true }), "mac")).toBeNull();
  });

  it("⌘⏎ 与 ⌘K 在输入框里仍生效：它们本来就是给输入用的", () => {
    expect(matchShortcut(ev("enter", { meta: true, inInput: true }), "mac")).toBe("send");
    expect(matchShortcut(ev("k", { meta: true, inInput: true }), "mac")).toBe(
      "commandPalette",
    );
  });

  it("页签切换在输入框里也不抢：打字时按 ⌘1 多半是手滑", () => {
    expect(matchShortcut(ev("1", { meta: true, inInput: true }), "mac")).toBeNull();
  });
});

describe("边界与纪律", () => {
  it("大写字母也认：Shift 按着不该让快捷键失灵", () => {
    expect(matchShortcut(ev("Z", { meta: true }), "mac")).toBe("undo");
  });

  it("没有匹配就是 null，NEVER 猜一个最近的", () => {
    expect(matchShortcut(ev("q", { meta: true }), "mac")).toBeNull();
  });

  it("撤销不在这里实现：派发给全局撤销栈（GRAPH-10）", () => {
    // 快捷键层自己维护一条撤销链，就会出现「按钮撤的和快捷键撤的不是同一件事」
    expect(CODE).not.toContain("undoStack");
    expect(CODE).not.toMatch(/const\s+stack/);
  });

  it("平台判定由外部传入：组件不嗅探 UA（与 GRAPH-13 同一条纪律）", () => {
    for (const forbidden of ["navigator.userAgent", "navigator.platform", "maxTouchPoints"]) {
      expect(CODE).not.toContain(forbidden);
    }
  });

  it("源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
