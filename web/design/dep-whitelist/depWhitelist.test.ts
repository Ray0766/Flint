// DESIGN-20 验收：样板依赖白名单（越界剥除 + 报错列出）。
//
// acceptance：**白名单外 script/link 剥除并报错列出**。
//
// 为什么要剥：样板是**模型生成**的，它见过无数带 CDN 引用的示例，于是很自然地
// 写出 `<script src="https://cdn.../chart.js">`。那一行的后果不是「多了个依赖」——
// 它让产物在客户机器上**向第三方发请求**：网络不通时页面塌掉、内容被对方看见、
// 而且哪天那个 CDN 改版，早已交付的文件会自己变样。
//
// 为什么剥完还要报错：静默剥除会让作者以为图表功能好好的，直到客户打开一个空白框。
// 剥 + 说清楚剥了什么，他才能换成自托管的做法。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import { codeOnly } from "../../test-utils/source";
import { DEFAULT_ALLOWED_ORIGINS, stripDisallowedDeps } from "./depWhitelist";

const CODE = codeOnly(readFileSync(join(__dirname, "depWhitelist.ts"), "utf8"));

describe("白名单本身", () => {
  it("默认只允许同源与 _ds 自托管资产", () => {
    expect([...DEFAULT_ALLOWED_ORIGINS]).toEqual(["self", "/_ds/"]);
  });
});

describe("stripDisallowedDeps（剥除 + 报错）", () => {
  it("剥掉外部 script，并报出剥了什么", () => {
    const html = [
      "<h1>标题</h1>",
      '<script src="https://cdn.example.com/chart.js"></script>',
      "<p>正文</p>",
    ].join("\n");

    const result = stripDisallowedDeps(html);

    expect(result.html).not.toContain("cdn.example.com");
    expect(result.removed).toEqual([
      { kind: "script", url: "https://cdn.example.com/chart.js" },
    ]);
  });

  it("剥掉外部 link（样式表/字体）同样报出来", () => {
    const html = '<link rel="stylesheet" href="https://fonts.example.com/x.css">';

    const result = stripDisallowedDeps(html);

    expect(result.html).not.toContain("fonts.example.com");
    expect(result.removed).toEqual([
      { kind: "link", url: "https://fonts.example.com/x.css" },
    ]);
  });

  it("同源与 _ds 资产保留：白名单不是「一律剥光」", () => {
    const html = [
      '<link rel="stylesheet" href="/_ds/flint/tokens/colors.css">',
      '<script src="/app/bundle.js"></script>',
    ].join("\n");

    const result = stripDisallowedDeps(html);

    expect(result.html).toBe(html);
    expect(result.removed).toEqual([]);
  });

  it("内联 script 不动：它不向外发请求，剥了反而毁掉页面自己的逻辑", () => {
    const html = "<script>document.title = 'x'</script>";

    const result = stripDisallowedDeps(html);

    expect(result.html).toBe(html);
    expect(result.removed).toEqual([]);
  });

  it("协议相对与 http 都算外部：`//cdn…` 是最容易漏的一种写法", () => {
    const html = [
      '<script src="//cdn.example.com/a.js"></script>',
      '<script src="http://cdn.example.com/b.js"></script>',
    ].join("\n");

    const result = stripDisallowedDeps(html);

    expect(result.removed.map((r) => r.url)).toEqual([
      "//cdn.example.com/a.js",
      "http://cdn.example.com/b.js",
    ]);
    expect(result.html).not.toContain("cdn.example.com");
  });

  it("data: 与 blob: 也剥：产物里嵌一段来路不明的可执行内容同样不该有", () => {
    const html = '<script src="data:text/javascript,alert(1)"></script>';

    const result = stripDisallowedDeps(html);

    expect(result.removed.map((r) => r.kind)).toEqual(["script"]);
  });

  it("剥除只动那一个标签：周围内容逐字不变", () => {
    const html = [
      "<h1>标题</h1>",
      '<script src="https://cdn.example.com/a.js"></script>',
      "<p>正文</p>",
    ].join("\n");

    const result = stripDisallowedDeps(html);

    expect(result.html).toContain("<h1>标题</h1>");
    expect(result.html).toContain("<p>正文</p>");
    expect(result.html.split("\n").filter((l) => l.trim()).length).toBe(2);
  });

  it("自定义白名单可放行指定来源（自托管镜像场景）", () => {
    const html = '<script src="https://assets.internal/a.js"></script>';

    const result = stripDisallowedDeps(html, ["self", "https://assets.internal/"]);

    expect(result.html).toBe(html);
    expect(result.removed).toEqual([]);
  });

  it("干净的样板原样返回（阴性对照：这把尺子不是见谁都剥）", () => {
    const html = "<h1>标题</h1><p>正文</p>";

    const result = stripDisallowedDeps(html);

    expect(result.html).toBe(html);
    expect(result.removed).toEqual([]);
  });

  it("剥除清单说得出「换成什么」：只说剥了等于把问题丢回给作者", () => {
    const result = stripDisallowedDeps(
      '<script src="https://cdn.example.com/a.js"></script>',
    );

    expect(result.action).toBeTruthy();
    expect(result.action).not.toBe("design.dep.action");
  });

  it("源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
