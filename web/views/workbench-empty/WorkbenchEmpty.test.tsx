// GRAPH-15 验收：工作台空态（从广场拖入引导）。
//
// acceptance：**空态文案 key 化；引导指向广场**。
//
// 空台不是错误态：一张还没放东西的画布是每个新用户的起点。所以这里给的是
// **一条出路**（去广场挑一个热点拖进来），而不是一句「暂无数据」——后者把用户留在原地。
// 这与 FAV-06（图书馆空态）是同一条纪律，路由常量也共用同一个来源：
// 两处各写一个字符串，改路由时必然漏掉一个。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PLAZA_ROUTE } from "../library-empty/LibraryEmpty";
import { codeOnly } from "../../test-utils/source";
import { WorkbenchEmpty } from "./WorkbenchEmpty";

const CODE = codeOnly(readFileSync(join(__dirname, "WorkbenchEmpty.tsx"), "utf8"));

describe("WorkbenchEmpty（工作台空态）", () => {
  it("引导指向广场，且用的是同一个路由常量", () => {
    render(<WorkbenchEmpty />);

    const cta = screen.getByTestId("workbench-empty-cta");
    expect(cta).toHaveAttribute("href", PLAZA_ROUTE);
    expect(PLAZA_ROUTE).toBe("/plaza");
    // 路由字符串在本文件里 NEVER 再写一遍：改路由时两处只会改一处
    expect(CODE).not.toContain('"/plaza"');
  });

  it("给的是一条可点的出路，不是一句「暂无数据」", () => {
    render(<WorkbenchEmpty />);

    const cta = screen.getByTestId("workbench-empty-cta");
    expect(cta.tagName.toLowerCase()).toBe("a");
    expect(cta.getAttribute("href")).toBeTruthy();
  });

  it("两条文案都取到了词条（t() 缺 key 时会回落成 key 本身）", () => {
    render(<WorkbenchEmpty />);

    const text = screen.getByTestId("workbench-empty-text").textContent ?? "";
    const cta = screen.getByTestId("workbench-empty-cta").textContent ?? "";

    expect(text).toBeTruthy();
    expect(cta).toBeTruthy();
    expect(text).not.toBe("workbench.empty");
    expect(cta).not.toBe("workbench.empty.cta");
  });

  it("说清怎么放东西进来：引导里带得出「拖入」这个动作", () => {
    render(<WorkbenchEmpty />);

    // 只说「去广场」而不说要做什么，用户到了广场还是不知道下一步；
    // 动作写在文案里（各语言各自表达），此处断言它带了动作提示槽
    expect(screen.getByTestId("workbench-empty-hint")).toBeInTheDocument();
    expect(screen.getByTestId("workbench-empty-hint").textContent).toBeTruthy();
  });

  it("空态不是错误态：不出现任何报错语义", () => {
    render(<WorkbenchEmpty />);

    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByTestId("workbench-empty").getAttribute("data-error")).toBeNull();
  });

  it("文案 key 化：源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
