// DESIGN-13 验收：后台检查三态（passed / failed / unreported）。
//
// acceptance：**三态视觉可区分（aria+class）；unreported 渲染 NEVER 等同 passed**。
//
// 为什么这条值得单独一张卡：`unreported` 是「这项检查没跑或没回话」，
// 它和「跑了、过了」是**两件相反的事**——一个是不知道，一个是知道没问题。
// 把不知道画成绿色，用户就会拿着一份「全绿」的界面去做决定，
// 而那些绿里有几格其实什么都没检查过。
//
// 这与 HOTSPOT-01 的「缺失逐槽隐藏 NEVER 占位」、DESIGN-12 的「失锚仍可见」
// 是同一条纪律：不确定的状态 NEVER 伪装成确定的。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { codeOnly } from "../../test-utils/source";
import { CHECK_STATES, CheckStatus, CheckSummary } from "./CheckStatus";

const CODE = codeOnly(readFileSync(join(__dirname, "CheckStatus.tsx"), "utf8"));

describe("CheckStatus（单项三态）", () => {
  it("三态就是这三个，一个不多一个不少", () => {
    expect([...CHECK_STATES]).toEqual(["passed", "failed", "unreported"]);
  });

  it("三态的 class 与 aria 各不相同：视觉与读屏都分得开", () => {
    const rendered = CHECK_STATES.map((state) => {
      const { unmount } = render(<CheckStatus name="contrast" state={state} />);
      const node = screen.getByTestId("check-status");
      const shape = {
        cls: node.className,
        role: node.getAttribute("role"),
        label: node.getAttribute("aria-label"),
        data: node.getAttribute("data-state"),
      };
      unmount();
      return shape;
    });

    expect(new Set(rendered.map((r) => r.cls)).size).toBe(3);
    expect(new Set(rendered.map((r) => r.label)).size).toBe(3);
    expect(rendered.map((r) => r.data)).toEqual([...CHECK_STATES]);
  });

  it("unreported 的每一处呈现都不等于 passed", () => {
    const { unmount } = render(<CheckStatus name="contrast" state="passed" />);
    const passed = screen.getByTestId("check-status");
    const passedShape = {
      cls: passed.className,
      label: passed.getAttribute("aria-label"),
      text: passed.textContent,
    };
    unmount();

    render(<CheckStatus name="contrast" state="unreported" />);
    const unreported = screen.getByTestId("check-status");

    expect(unreported.className).not.toBe(passedShape.cls);
    expect(unreported.getAttribute("aria-label")).not.toBe(passedShape.label);
    expect(unreported.textContent).not.toBe(passedShape.text);
  });

  it("unreported 不靠颜色说话：aria-label 里明说没有结果", () => {
    render(<CheckStatus name="contrast" state="unreported" />);

    const label = screen.getByTestId("check-status").getAttribute("aria-label") ?? "";
    expect(label).toBeTruthy();
    expect(label).not.toBe("design.check.unreported");   // 取到了词条
  });

  it("未知状态不当成 passed：宁可报错也不画一格绿", () => {
    expect(() =>
      // @ts-expect-error 故意传一个不在三态里的值
      render(<CheckStatus name="contrast" state="ok" />),
    ).toThrow();
  });

  it("检查名如实带出：用户要知道是哪一项没跑", () => {
    render(<CheckStatus name="contrast" state="unreported" />);

    expect(screen.getByTestId("check-status")).toHaveAttribute("data-check", "contrast");
  });
});

describe("CheckSummary（汇总）", () => {
  const CHECKS = [
    { name: "contrast", state: "passed" as const },
    { name: "alt-text", state: "unreported" as const },
    { name: "tap-target", state: "failed" as const },
  ];

  it("汇总把三态分开计数，unreported 不并进 passed", () => {
    render(<CheckSummary checks={CHECKS} />);

    const bar = screen.getByTestId("check-summary");
    expect(bar).toHaveAttribute("data-passed", "1");
    expect(bar).toHaveAttribute("data-failed", "1");
    expect(bar).toHaveAttribute("data-unreported", "1");
  });

  it("有 unreported 时整体不算「全过」：那是不知道，不是没问题", () => {
    render(<CheckSummary checks={CHECKS.filter((c) => c.state !== "failed")} />);

    expect(screen.getByTestId("check-summary")).toHaveAttribute("data-all-passed", "false");
  });

  it("全 passed 才是全过（阴性对照）", () => {
    render(<CheckSummary checks={[{ name: "contrast", state: "passed" }]} />);

    expect(screen.getByTestId("check-summary")).toHaveAttribute("data-all-passed", "true");
  });

  it("空清单不是全过：一项都没有时 NEVER 显示成通过", () => {
    render(<CheckSummary checks={[]} />);

    expect(screen.getByTestId("check-summary")).toHaveAttribute("data-all-passed", "false");
  });

  it("源码里没有把 unreported 折算成 passed 的写法", () => {
    expect(CODE).not.toMatch(/unreported[^\n]*passed/);
    expect(CODE).not.toMatch(/state\s*!==\s*"failed"/);   // 「不是失败就算过」
  });

  it("文案 key 化：源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
