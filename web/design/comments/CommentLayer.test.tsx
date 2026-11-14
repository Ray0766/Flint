// DESIGN-12 验收（前端半）：评论 data-loc 锚 + 元素消失降级坐标锚。
//
// acceptance①「元素消失 → 坐标锚降级仍可见」。
//
// 为什么必须降级而不是隐藏：用户写下那句话时，页面还长着另一个样子。
// 后来那个元素被改没了，评论就**没了着落**——若此时把它藏起来，
// 用户会以为自己的意见被系统吃掉了；而它其实还在，只是钉不住原来那个位置。
// 降级到坐标锚是如实的：位置可能不准，但那句话还在，且明说了它已经失锚。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { codeOnly } from "../../test-utils/source";
import { CommentLayer, resolveAnchor } from "./CommentLayer";

const CODE = codeOnly(readFileSync(join(__dirname, "CommentLayer.tsx"), "utf8"));

const HTML = '<section data-loc="3:1"><h1 data-loc="4:3">燧石</h1></section>';

const COMMENTS = [
  { commentId: "c-1", text: "这里太挤了", loc: "4:3", point: null, resolved: false },
  { commentId: "c-2", text: "配色偏冷", loc: "9:9", point: [120, 340] as [number, number], resolved: false },
];

describe("resolveAnchor（锚解析）", () => {
  it("元素还在：用 data-loc 锚，标记未降级", () => {
    const anchor = resolveAnchor(HTML, COMMENTS[0]);

    expect(anchor.kind).toBe("element");
    expect(anchor.loc).toBe("4:3");
    expect(anchor.degraded).toBe(false);
  });

  it("元素没了：降级到坐标锚，且**明说**已降级", () => {
    const anchor = resolveAnchor(HTML, COMMENTS[1]);

    expect(anchor.kind).toBe("point");
    expect(anchor.point).toEqual([120, 340]);
    expect(anchor.degraded).toBe(true);
  });

  it("元素没了又没有坐标：标为失锚，NEVER 假装它还钉在某处", () => {
    const anchor = resolveAnchor(HTML, {
      commentId: "c-3", text: "x", loc: "9:9", point: null, resolved: false,
    });

    expect(anchor.kind).toBe("orphan");
    expect(anchor.degraded).toBe(true);
  });
});

describe("CommentLayer（渲染）", () => {
  it("元素消失的评论仍然可见：藏起来等于把用户的意见吃掉", () => {
    render(<CommentLayer html={HTML} comments={COMMENTS} onRequestAi={() => {}} />);

    const items = screen.getAllByTestId("design-comment");
    expect(items).toHaveLength(2);
    expect(items[1]).toHaveAttribute("data-anchor-kind", "point");
    expect(items[1]).toHaveAttribute("data-degraded", "true");
    expect(within(items[1]).getByText(/配色偏冷/)).toBeInTheDocument();
  });

  it("降级的评论带得出提示：位置可能不准这件事要说出来", () => {
    render(<CommentLayer html={HTML} comments={COMMENTS} onRequestAi={() => {}} />);

    const degraded = screen.getByTestId("design-comment-degraded-note");
    expect(degraded.textContent).toBeTruthy();
    expect(degraded.textContent).not.toBe("design.comment.degraded");
  });

  it("没降级的评论不挂那条提示：常驻提示等于没有提示", () => {
    render(
      <CommentLayer html={HTML} comments={[COMMENTS[0]]} onRequestAi={() => {}} />,
    );

    expect(screen.queryByTestId("design-comment-degraded-note")).toBeNull();
  });

  it("「让 AI 处理」把这一条交出去，带上它的锚", () => {
    const requested: unknown[] = [];
    render(
      <CommentLayer
        html={HTML}
        comments={COMMENTS}
        onRequestAi={(payload) => requested.push(payload)}
      />,
    );

    const items = screen.getAllByTestId("design-comment");
    within(items[0]).getByTestId("design-comment-ai").click();

    expect(requested).toEqual([
      { commentId: "c-1", loc: "4:3", point: null },
    ]);
  });

  it("失锚的评论不给「让 AI 处理」：指不出地方的意见交给模型只会让它凭空动手", () => {
    render(
      <CommentLayer
        html={HTML}
        comments={[{ commentId: "c-3", text: "x", loc: "9:9", point: null, resolved: false }]}
        onRequestAi={() => {}}
      />,
    );

    expect(screen.queryByTestId("design-comment-ai")).toBeNull();
  });

  it("已解决的评论不渲染在层上：留着会把画布堆满旧意见", () => {
    render(
      <CommentLayer
        html={HTML}
        comments={[{ ...COMMENTS[0], resolved: true }]}
        onRequestAi={() => {}}
      />,
    );

    expect(screen.queryAllByTestId("design-comment")).toHaveLength(0);
  });

  it("评论层不改 HTML：它只是覆在上面的一层", () => {
    for (const banned of ["applyEdit", "stripDataLoc", "innerHTML", "replace("]) {
      expect(CODE).not.toContain(banned);
    }
  });

  it("文案 key 化：源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
