// FAV-06 验收：空态文案全 key 化；引导跳转指向广场路由。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LibraryEmpty, PLAZA_ROUTE } from "./LibraryEmpty";

describe("LibraryEmpty", () => {
  it("引导跳转指向广场路由", () => {
    render(<LibraryEmpty />);
    expect(PLAZA_ROUTE).toBe("/plaza");
    expect(screen.getByTestId("library-empty-cta")).toHaveAttribute("href", "/plaza");
  });

  it("文案全 key 化：源码代码行里无 CJK", () => {
    const source = readFileSync(join(__dirname, "LibraryEmpty.tsx"), "utf8");
    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .split("\n")
      .filter((l) => !l.trim().startsWith("//"))
      .join("\n");
    expect(code).not.toMatch(/[\u4e00-\u9fff]/);
  });

  it("两条文案都取到了内容（key 缺失时 t() 会回落成 key 本身）", () => {
    render(<LibraryEmpty />);
    const text = screen.getByTestId("library-empty-text").textContent ?? "";
    const cta = screen.getByTestId("library-empty-cta").textContent ?? "";
    expect(text).toBeTruthy();
    expect(cta).toBeTruthy();
    // 回落形态是「key 原样」，出现点号说明没取到词条
    expect(text).not.toBe("library.empty");
    expect(cta).not.toBe("library.empty.cta");
  });

  it("空态给的是**出路**而不是「暂无数据」：必须有可点的跳转", () => {
    render(<LibraryEmpty />);
    const cta = screen.getByTestId("library-empty-cta");
    expect(cta.tagName.toLowerCase()).toBe("a");
    expect(cta.getAttribute("href")).toBeTruthy();
  });
});
