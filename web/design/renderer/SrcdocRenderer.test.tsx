// DESIGN-02 验收：渲染管线 iframe.srcdoc 零构建（禁 Babel/构建器）。
//
// acceptance：**srcdoc 直挂；Babel/构建器 import 黑名单零命中**。
//
// 为什么零构建：把生成的 HTML 拿去转译，等于让预览与最终产物**不是同一份东西**——
// 用户在预览里调好的样子，导出时可能因为转译差异变形。srcdoc 直挂时，
// 预览里那段字节就是最终那段字节。
//
// 为什么必须 sandbox：srcdoc 里的内容是**模型生成的**。不设沙箱的话，
// 它与主页面同源——能读 cookie、能发请求、能改主界面。这不是「理论风险」：
// 生成内容里出现一段 fetch 是完全正常的事，因为模型见过无数带 fetch 的示例。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { codeOnly } from "../../test-utils/source";
import { SANDBOX_FLAGS, SrcdocRenderer } from "./SrcdocRenderer";

const CODE = codeOnly(readFileSync(join(__dirname, "SrcdocRenderer.tsx"), "utf8"));
const PKG = JSON.parse(
  readFileSync(join(__dirname, "..", "..", "package.json"), "utf8"),
) as { dependencies: Record<string, string>; devDependencies: Record<string, string> };

const HTML = "<h1>燧石</h1><p>供应链</p>";

describe("SrcdocRenderer（零构建预览）", () => {
  it("HTML 逐字挂进 srcdoc：预览里那段字节就是最终那段字节", () => {
    render(<SrcdocRenderer html={HTML} />);

    const frame = screen.getByTestId("design-srcdoc-frame");
    expect(frame.getAttribute("srcdoc")).toBe(HTML);
  });

  it("NEVER 转译：源码里不出现任何转译/构建入口", () => {
    for (const banned of [
      "@babel", "babel", "transform(", "sucrase", "esbuild", "swc",
      "new Function", "eval(",
    ]) {
      expect(CODE.toLowerCase()).not.toContain(banned.toLowerCase());
    }
  });

  it("package.json 里没有转译器依赖（黑名单零命中）", () => {
    const all = Object.keys({ ...PKG.dependencies, ...PKG.devDependencies });

    for (const banned of [
      "@babel/core", "@babel/standalone", "babel-standalone",
      "sucrase", "esbuild", "@swc/core", "typescript-transform-paths",
    ]) {
      expect(all).not.toContain(banned);
    }
  });

  it("沙箱标志显式且不含 allow-same-origin", () => {
    render(<SrcdocRenderer html={HTML} />);

    const frame = screen.getByTestId("design-srcdoc-frame");
    const flags = (frame.getAttribute("sandbox") ?? "").split(" ").filter(Boolean);

    expect(flags).toEqual([...SANDBOX_FLAGS]);
    // allow-same-origin + allow-scripts = 沙箱形同虚设（脚本能自己摘掉沙箱）
    expect(flags).not.toContain("allow-same-origin");
    expect(flags).not.toContain("allow-top-navigation");
  });

  it("空 HTML 渲染空预览而不是不渲染：那是「还没生成」的可见状态", () => {
    render(<SrcdocRenderer html="" />);

    expect(screen.getByTestId("design-srcdoc-frame")).toBeInTheDocument();
    expect(screen.getByTestId("design-srcdoc-frame").getAttribute("srcdoc")).toBe("");
  });

  it("换 HTML 就换 srcdoc：预览跟着内容走", () => {
    const { rerender } = render(<SrcdocRenderer html={HTML} />);

    rerender(<SrcdocRenderer html="<h1>新的</h1>" />);

    expect(screen.getByTestId("design-srcdoc-frame").getAttribute("srcdoc")).toBe(
      "<h1>新的</h1>",
    );
  });

  it("HTML 不被「清洗」后再挂：预览要显示的就是模型给的那份", () => {
    // 悄悄改写生成内容（比如删掉 style），会让用户调好的样子在导出时又变回来
    const tricky = '<div style="color:red" onclick="x()">a<script>1</script></div>';
    render(<SrcdocRenderer html={tricky} />);

    expect(screen.getByTestId("design-srcdoc-frame").getAttribute("srcdoc")).toBe(tricky);
    // 安全靠沙箱，不靠改写内容——改写只会制造「预览与产物不一致」
    expect(CODE).not.toContain("replace(/<script");
  });

  it("标题可读：iframe 带 title，读屏能说出这是什么", () => {
    render(<SrcdocRenderer html={HTML} />);

    const title = screen.getByTestId("design-srcdoc-frame").getAttribute("title") ?? "";
    expect(title).toBeTruthy();
    expect(title).not.toBe("design.renderer.title");
  });

  it("文案 key 化：源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
