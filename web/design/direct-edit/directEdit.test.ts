// DESIGN-10 验收：直接编辑（data-loc 定位 + 落点顺序 + 导出剥离）。
//
// acceptance①「落点顺序 工具类→style，全局 CSS 写入路径不存在」；
// acceptance②「导出产物零 data-loc 属性」。
//
// 为什么落点有顺序：同一处改动可以落在三个地方，而它们的**影响半径**天差地别——
// 工具类只影响这一个元素、inline style 也只影响这一个、全局 CSS 影响**所有**长得像的元素。
// 用户点着一张卡片说「这里紧一点」，改的却是全站所有卡片，那是他绝不会预期的。
// 所以全局 CSS 这条路**根本不存在**，而不是「排在最后」。
//
// 为什么导出要剥 data-loc：那是编辑器给自己用的定位锚。留在产物里等于把开发期的
// 脚手架交付给客户，而且下一次导入时这些锚会与新的编辑器状态对不上号。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { codeOnly } from "../../test-utils/source";
import {
  applyEdit,
  exportHtml,
  findByLoc,
  LANDING_ORDER,
  stripDataLoc,
} from "./directEdit";

const CODE = codeOnly(readFileSync(join(__dirname, "directEdit.ts"), "utf8"));

const HTML = [
  "<section data-loc=\"3:1\" class=\"card p-4\">",
  "  <h1 data-loc=\"4:3\" class=\"title\">燧石</h1>",
  "  <p data-loc=\"5:3\" style=\"color: var(--ink-2)\">供应链</p>",
  "</section>",
].join("\n");

describe("data-loc 定位", () => {
  it("按 loc 找到的是那个元素的**开标签**，且不吞正文", () => {
    const found = findByLoc(HTML, "4:3");
    const tag = HTML.slice(found!.start, found!.end);

    expect(found).not.toBeNull();
    expect(tag).toBe('<h1 data-loc="4:3" class="title">');
    // 区间越大，回写时越容易碰到正文——属性编辑只需要开标签这一段
    expect(tag).not.toContain("燧石");
    expect(tag.endsWith(">")).toBe(true);
  });

  it("loc 不存在时返回 null：NEVER 退而求其次改一个「差不多的」元素", () => {
    expect(findByLoc(HTML, "99:9")).toBeNull();
  });
});

describe("落点顺序：工具类 → inline style，没有第三条路", () => {
  it("顺序表就是两级，全局 CSS 不在其中", () => {
    expect([...LANDING_ORDER]).toEqual(["utility-class", "inline-style"]);
    expect(LANDING_ORDER).not.toContain("global-css");
  });

  it("能用工具类表达就落工具类（影响半径最小）", () => {
    const next = applyEdit(HTML, { loc: "3:1", utilityClass: "p-6", style: null });

    expect(next).toContain('class="card p-4 p-6"');
    expect(next).not.toContain("<style");
  });

  it("工具类表达不了才落 inline style", () => {
    const next = applyEdit(HTML, {
      loc: "5:3",
      utilityClass: null,
      style: { color: "var(--rust)" },
    });

    expect(next).toContain("color: var(--rust)");
    expect(next).not.toContain("<style");
  });

  it("两者都给时优先工具类：顺序是硬的，不由调用方临场决定", () => {
    const next = applyEdit(HTML, {
      loc: "3:1",
      utilityClass: "gap-2",
      style: { gap: "8px" },
    });

    expect(next).toContain("gap-2");
    expect(next).not.toContain("gap: 8px");
  });

  it("全局 CSS 写入路径**不存在**：没有那个入参，源码里也没有那条分支", () => {
    expect(() =>
      // @ts-expect-error 故意传一个不存在的落点，签名上就不该有它
      applyEdit(HTML, { loc: "3:1", globalCss: ".card{padding:24px}" }),
    ).toThrow();
    for (const banned of ["globalCss", "<style", "styleSheet", "insertRule"]) {
      expect(CODE).not.toContain(banned);
    }
  });

  it("两个落点都没给时报错：一次什么都不改的编辑是调用方算错了", () => {
    expect(() =>
      applyEdit(HTML, { loc: "3:1", utilityClass: null, style: null }),
    ).toThrow();
  });

  it("改动只落在那一个元素上：其它行逐字不变", () => {
    const next = applyEdit(HTML, { loc: "4:3", utilityClass: "text-lg", style: null });
    const before = HTML.split("\n");
    const after = next.split("\n");

    expect(after).toHaveLength(before.length);
    expect(after[0]).toBe(before[0]);
    expect(after[2]).toBe(before[2]);
    expect(after[1]).not.toBe(before[1]);
  });
});

describe("导出剥离 data-loc", () => {
  it("导出产物零 data-loc", () => {
    const exported = exportHtml(HTML);

    expect(exported).not.toContain("data-loc");
    expect(stripDataLoc(HTML)).toBe(exported);
  });

  it("只剥 data-loc，别的属性一个不动", () => {
    const exported = exportHtml(HTML);

    expect(exported).toContain('class="card p-4"');
    expect(exported).toContain('style="color: var(--ink-2)"');
    expect(exported).toContain("燧石");
    expect(exported).toContain("供应链");
  });

  it("剥离不留双空格：`<h1 data-loc=\"x\" class=` 剥完不该变成 `<h1  class=`", () => {
    const exported = exportHtml(HTML);

    expect(exported).not.toMatch(/<\w+\s{2,}/);
  });

  it("单引号与无引号写法也剥得掉：产物里 NEVER 漏一个锚点", () => {
    const messy = "<div data-loc='1:1'><b data-loc=2:2>x</b></div>";

    expect(stripDataLoc(messy)).not.toContain("data-loc");
  });

  it("源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
