// DESIGN-07 验收：澄清问题卡（每题「由你决定」+ 全局一键 + 未答禁续输）。
//
// acceptance：**每题带「由你决定」；全局「全部由你决定」一键；未答复输入框禁用**。
//
// 为什么「由你决定」必须每题都有：澄清问题里总有几条用户其实无所谓——
// 逼他在无所谓的事上做选择，他要么随便点一个（于是系统拿到一个假答案），
// 要么干脆放弃这一轮。把「你替我定」做成一个正经选项，拿到的是**真实**的授权。
//
// 为什么未答复要禁输入：让他一边留着没答的问题一边继续说，系统就得猜
// 「这句新话是不是在回答刚才那题」——猜错的代价是整轮生成基于一个错误前提。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { codeOnly } from "../../test-utils/source";
import { ClarifyCards } from "./ClarifyCards";

const CODE = codeOnly(readFileSync(join(__dirname, "ClarifyCards.tsx"), "utf8"));

const QUESTIONS = [
  { id: "q1", question: "配色走冷调还是暖调", options: ["冷调", "暖调"] },
  { id: "q2", question: "首屏要不要大字标题", options: ["要", "不要"] },
  { id: "q3", question: "数据表默认展开几行", options: ["5 行", "10 行"] },
];

function setup(overrides: Record<string, unknown> = {}) {
  const onAnswer = vi.fn();
  const onDeferAll = vi.fn();
  render(
    <ClarifyCards
      questions={QUESTIONS}
      answers={{}}
      onAnswer={onAnswer}
      onDeferAll={onDeferAll}
      {...overrides}
    />,
  );
  return { onAnswer, onDeferAll };
}

describe("ClarifyCards（澄清卡）", () => {
  it("每题都带「由你决定」，一题不落", () => {
    setup();

    const cards = screen.getAllByTestId("clarify-card");
    expect(cards).toHaveLength(3);
    for (const card of cards) {
      expect(within(card).getByTestId("clarify-defer")).toBeInTheDocument();
    }
  });

  it("点某题的「由你决定」= 给出一个**明确的**答案，不是留空", () => {
    const { onAnswer } = setup();

    const card = screen.getAllByTestId("clarify-card")[1];
    fireEvent.click(within(card).getByTestId("clarify-defer"));

    expect(onAnswer).toHaveBeenCalledWith("q2", { deferred: true, choice: null });
    // 留空与「你替我定」是两件事：前者是没答，后者是答了「你定」
  });

  it("选了具体选项就带着那个选项回去", () => {
    const { onAnswer } = setup();

    const card = screen.getAllByTestId("clarify-card")[0];
    fireEvent.click(within(card).getAllByTestId("clarify-option")[1]);

    expect(onAnswer).toHaveBeenCalledWith("q1", { deferred: false, choice: "暖调" });
  });

  it("全局「全部由你决定」一键把**所有未答**的题一起交出去", () => {
    const { onDeferAll } = setup({
      answers: { q1: { deferred: false, choice: "冷调" } },
    });

    fireEvent.click(screen.getByTestId("clarify-defer-all"));

    expect(onDeferAll).toHaveBeenCalledTimes(1);
    // 已答的 q1 不被覆盖：一键是「剩下的你定」，不是「推翻我刚才说的」
    expect(onDeferAll).toHaveBeenCalledWith(["q2", "q3"]);
  });

  it("全部答完后全局按钮消失：没有「剩下的」可交待", () => {
    setup({
      answers: {
        q1: { deferred: false, choice: "冷调" },
        q2: { deferred: true, choice: null },
        q3: { deferred: false, choice: "5 行" },
      },
    });

    expect(screen.queryByTestId("clarify-defer-all")).toBeNull();
  });

  it("有未答题时输入框禁用，且说明为什么", () => {
    setup();

    const input = screen.getByTestId("clarify-blocked-input");
    expect(input).toBeDisabled();
    const why = screen.getByTestId("clarify-blocked-reason");
    expect(why.textContent).toBeTruthy();
    expect(why.textContent).not.toBe("design.clarify.blocked");
  });

  it("全部答完（含「由你决定」）输入框解禁：deferred 也算答", () => {
    setup({
      answers: {
        q1: { deferred: true, choice: null },
        q2: { deferred: true, choice: null },
        q3: { deferred: true, choice: null },
      },
    });

    expect(screen.getByTestId("clarify-blocked-input")).toBeEnabled();
    expect(screen.queryByTestId("clarify-blocked-reason")).toBeNull();
  });

  it("未答计数如实：用户要知道还差几题", () => {
    setup({ answers: { q1: { deferred: false, choice: "冷调" } } });

    expect(screen.getByTestId("clarify-pending-count")).toHaveAttribute(
      "data-pending", "2",
    );
  });

  it("没有问题时整个卡组不渲染：零题不该占一块空白", () => {
    render(
      <ClarifyCards questions={[]} answers={{}} onAnswer={vi.fn()} onDeferAll={vi.fn()} />,
    );

    expect(screen.queryByTestId("clarify-cards")).toBeNull();
  });

  it("组件不自己攒答案：答案由上层持有（单一真相）", () => {
    // 组件内部另存一份 answers，会与上层那份漂移：用户看到的与将要发出去的不是同一份
    expect(CODE).not.toMatch(/useState<[^>]*Answer/);
    expect(CODE).not.toContain("setAnswers");
  });

  it("文案 key 化：源码代码行零 CJK", () => {
    expect(CODE).not.toMatch(/[一-鿿]/);
  });
});
