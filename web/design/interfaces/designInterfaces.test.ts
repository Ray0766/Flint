// DESIGN-03 验收（G11）：三接口抽象 —— Html* 唯一实现，Jsx* 存在但抛未实现。
//
// acceptance：**HtmlRenderer/HtmlPatcher/HtmlExporter 可用；Jsx 三接口存在且抛 NotImplementedError**。
//
// 为什么要留三个会抛错的 Jsx 接口，而不是干脆不写：接口位置**先定下来**，
// 将来接 JSX 产物时改的是实现而不是调用点；而抛错保证了「它现在没有」这件事
// 在运行时是**响亮的**——一个返回空字符串的假实现会让上层以为渲染成功了，
// 然后把一片空白当成产物导出去。
//
// 这与 SCHEMA-11 的 friend 缝是同一条纪律：NEVER 用 flag 或空返回占位。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { codeOnly } from "../../test-utils/source";
import {
  HtmlExporter,
  HtmlPatcher,
  HtmlRenderer,
  JsxExporter,
  JsxPatcher,
  JsxRenderer,
  NotImplementedError,
} from "./designInterfaces";

const CODE = codeOnly(readFileSync(join(__dirname, "designInterfaces.ts"), "utf8"));

const HTML = '<section class="card"><h1>燧石</h1></section>';

describe("Html*（唯一实现）", () => {
  it("HtmlRenderer 原样交出 HTML：渲染层零改写（承 DESIGN-02 的零构建口径）", () => {
    expect(new HtmlRenderer().render(HTML)).toBe(HTML);
  });

  it("HtmlPatcher 按字节区间回写，其余字节一个不动", () => {
    const patched = new HtmlPatcher().patch(HTML, {
      start: HTML.indexOf("燧石"),
      end: HTML.indexOf("燧石") + 2,
      text: "Flint",
    });

    expect(patched).toBe('<section class="card"><h1>Flint</h1></section>');
    // 区间外逐字不变：整段重写会把用户手改过的地方一起冲掉
    expect(patched.startsWith('<section class="card"><h1>')).toBe(true);
    expect(patched.endsWith("</h1></section>")).toBe(true);
  });

  it("HtmlPatcher 拒绝越界与倒置区间：那是调用方算错了，NEVER 猜他想改哪", () => {
    const patcher = new HtmlPatcher();

    expect(() => patcher.patch(HTML, { start: -1, end: 3, text: "x" })).toThrow();
    expect(() => patcher.patch(HTML, { start: 3, end: 2, text: "x" })).toThrow();
    expect(() =>
      patcher.patch(HTML, { start: 0, end: HTML.length + 1, text: "x" }),
    ).toThrow();
  });

  it("HtmlExporter 导出的字节与输入逐字相同：导出不是二次渲染", () => {
    expect(new HtmlExporter().export(HTML)).toBe(HTML);
  });

  it("三个 Html 实现都不改内容长度以外的东西（无清洗、无格式化）", () => {
    const messy = "<div  style='a:b'   >x</div>";

    expect(new HtmlRenderer().render(messy)).toBe(messy);
    expect(new HtmlExporter().export(messy)).toBe(messy);
    for (const banned of ["prettier", "format(", "sanitize", "minify"]) {
      expect(CODE.toLowerCase()).not.toContain(banned);
    }
  });
});

describe("Jsx*（缝，存在但未实现）", () => {
  it("三个 Jsx 接口都在，且调用即抛未实现", () => {
    expect(() => new JsxRenderer().render(HTML)).toThrow(NotImplementedError);
    expect(() =>
      new JsxPatcher().patch(HTML, { start: 0, end: 1, text: "x" }),
    ).toThrow(NotImplementedError);
    expect(() => new JsxExporter().export(HTML)).toThrow(NotImplementedError);
  });

  it("错误信息说清是什么没做，而不是一句 error", () => {
    try {
      new JsxRenderer().render(HTML);
      throw new Error("NEVER 该走到这里");
    } catch (err) {
      expect((err as Error).message).toContain("jsx");
      expect((err as Error).message).toContain("post-v1");
    }
  });

  it("NEVER 用空返回或 flag 占位：源码里没有「返回空串」式的假实现", () => {
    expect(CODE).not.toMatch(/return\s*""\s*;/);
    expect(CODE).not.toMatch(/enabled\s*[:=]\s*false/);
  });

  it("Jsx 与 Html 是同一组签名：将来换实现时调用点一个字都不用改", () => {
    const html = new HtmlRenderer();
    const jsx = new JsxRenderer();

    expect(typeof jsx.render).toBe(typeof html.render);
    expect(jsx.render.length).toBe(html.render.length);
    expect(new JsxPatcher().patch.length).toBe(new HtmlPatcher().patch.length);
    expect(new JsxExporter().export.length).toBe(new HtmlExporter().export.length);
  });

  it("文案 key 化不适用（本模块无界面文案），但源码代码行仍零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
