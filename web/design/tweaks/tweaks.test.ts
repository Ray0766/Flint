// DESIGN-08 验收：Tweaks 快路径（拖动只 patch CSS 变量）+ 字节区间回写。
//
// acceptance①「拖动只 patch CSS 变量（srcdoc 重建 spy=0）」；
// acceptance②「回写按字节区间、缩进保持（diff 最小断言）」。
//
// 为什么拖动不能重建 srcdoc：重建等于整页重新加载——滚动位置回到顶部、
// 动画从头播、iframe 里的输入框失焦。用户拖着一个滑块调间距，
// 每动一格页面就跳一次，那个面板根本没法用。
//
// 为什么回写要按字节区间：整段重写会把用户手改过的地方一起冲掉，
// 也会让 diff 变成「整文件变了」——之后没有人能一眼看出这次到底动了什么。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it, vi } from "vitest";

import { codeOnly } from "../../test-utils/source";
import { applyTweak, findVariableSpan, patchSource } from "./tweaks";

const CODE = codeOnly(readFileSync(join(__dirname, "tweaks.ts"), "utf8"));

const SOURCE = [
  "<style>",
  "  :root {",
  "    --gap: 12px;",
  "    --accent: var(--indigo);",
  "  }",
  "</style>",
  '<div class="card">内容</div>',
].join("\n");

describe("快路径：拖动只 patch CSS 变量", () => {
  it("拖动调用的是 setProperty，srcdoc 一次都不重建", () => {
    const setProperty = vi.fn();
    const rebuildSrcdoc = vi.fn();
    const style = { setProperty } as unknown as CSSStyleDeclaration;

    applyTweak({ name: "--gap", value: "16px" }, { style, rebuildSrcdoc });
    applyTweak({ name: "--gap", value: "20px" }, { style, rebuildSrcdoc });
    applyTweak({ name: "--gap", value: "24px" }, { style, rebuildSrcdoc });

    expect(setProperty).toHaveBeenCalledTimes(3);
    expect(setProperty).toHaveBeenLastCalledWith("--gap", "24px");
    expect(rebuildSrcdoc).not.toHaveBeenCalled();   // spy = 0
  });

  it("只认 CSS 变量：普通属性名走不了快路径（那需要改结构，不是改一个值）", () => {
    const style = { setProperty: vi.fn() } as unknown as CSSStyleDeclaration;

    expect(() =>
      applyTweak({ name: "padding", value: "16px" }, { style, rebuildSrcdoc: vi.fn() }),
    ).toThrow();
  });

  it("空值不下发：把变量设成空串等于把那条样式抹掉，而用户只是拖到了最左", () => {
    const style = { setProperty: vi.fn() } as unknown as CSSStyleDeclaration;

    expect(() =>
      applyTweak({ name: "--gap", value: "" }, { style, rebuildSrcdoc: vi.fn() }),
    ).toThrow();
  });

  it("源码里没有重建 srcdoc 的写法（srcdoc 赋值/innerHTML）", () => {
    for (const banned of ["srcdoc =", "srcDoc =", "innerHTML"]) {
      expect(CODE).not.toContain(banned);
    }
  });
});

describe("落盘：按字节区间回写", () => {
  it("找得到变量的**值**所在区间，且区间只覆盖值本身", () => {
    const span = findVariableSpan(SOURCE, "--gap");

    expect(span).not.toBeNull();
    expect(SOURCE.slice(span!.start, span!.end)).toBe("12px");
  });

  it("回写只改那一段，其余字节逐字不变", () => {
    const patched = patchSource(SOURCE, "--gap", "16px");

    expect(patched).toBe(SOURCE.replace("--gap: 12px", "--gap: 16px"));
    // diff 最小：行数不变、缩进不变
    expect(patched.split("\n")).toHaveLength(SOURCE.split("\n").length);
    expect(patched.split("\n")[2]).toBe("    --gap: 16px;");
  });

  it("缩进保持：四空格的那一行改完还是四空格", () => {
    const patched = patchSource(SOURCE, "--accent", "var(--sulfur)");

    expect(patched.split("\n")[3]).toBe("    --accent: var(--sulfur);");
  });

  it("同名变量出现多次时只改第一处定义，NEVER 一把全替", () => {
    const twice = SOURCE + "\n<style>.x{--gap: 4px}</style>";

    const patched = patchSource(twice, "--gap", "16px");

    expect(patched).toContain("--gap: 16px;");
    expect(patched).toContain("--gap: 4px");    // 第二处原样留着
  });

  it("变量不存在时报错而不是悄悄追加一条定义", () => {
    // 悄悄追加会让源码里多出一条用户从没写过的规则，而他以为自己只是拖了个滑块
    expect(() => patchSource(SOURCE, "--nope", "1px")).toThrow();
    expect(findVariableSpan(SOURCE, "--nope")).toBeNull();
  });

  it("引用不算定义：var(--gap) 不会被当成可回写的位置", () => {
    const onlyRef = ".a{padding:var(--gap)}";

    expect(findVariableSpan(onlyRef, "--gap")).toBeNull();
  });

  it("值里带 var() 也能整体换掉（区间到分号前为止）", () => {
    const span = findVariableSpan(SOURCE, "--accent");

    expect(SOURCE.slice(span!.start, span!.end)).toBe("var(--indigo)");
  });

  it("回写不碰内容文本：HTML 正文一个字节不动", () => {
    const patched = patchSource(SOURCE, "--gap", "16px");

    expect(patched).toContain('<div class="card">内容</div>');
  });

  it("源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
