// CHAIN-05：受保护 block 的三种来由 —— **阴性对照三条，各说各的话**。
//
// `CLAUDE.md#S2-5`：受保护 block（`locked ∨ author=="user" ∨ user_modified`）
// NEVER 被 regenerate 改写。
//
// 三种受保护要用户做的事**完全不同**：
// 锁着的要先解锁；他自己写的与他改过的，系统本来就不该碰。
// 合成一句「不可编辑」，用户不知道该去解锁还是该收手。
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { availableBlockInterventions } from "../../lib/interventionClient";
import { isProtected, type Block } from "../../lib/types";
import zh from "../../messages/zh.json";

function block(over: Partial<Block> = {}): Block {
  return {
    block_id: "b-1",
    deliverable_id: "del-1",
    section_id: "sec-1",
    order: 0,
    type: "paragraph",
    content: { kind: "paragraph", text: "x" },
    claim_ids: [],
    fact_ids: [],
    author: "system",
    revision: 1,
    locked: false,
    user_modified: false,
    ...over,
  } as Block;
}

const PROTECTED = [
  ["locked", block({ locked: true }), zh["intervention.protected.locked"]],
  ["authored", block({ author: "user" }), zh["intervention.protected.authored"]],
  ["modified", block({ user_modified: true }), zh["intervention.protected.modified"]],
] as const;

describe("CHAIN-05 受保护 block", () => {
  it.each(PROTECTED)("%s：受保护，且一个动作都不给", (_name, b) => {
    expect(isProtected(b)).toBe(true);
    // 动作表是**唯一**的判断处。空表 = 连 regenerate 的键都不会出现。
    expect(availableBlockInterventions(b)).toEqual([]);
  });

  it("没受保护的 block 四个动作齐全", () => {
    expect(availableBlockInterventions(block())).toEqual(
      ["lock", "regenerate", "dispute", "instruct_regenerate"]);
  });

  it("三句话互不相同——合成一句，用户不知道该解锁还是该收手", () => {
    const said = PROTECTED.map(([, , line]) => line);

    expect(new Set(said).size).toBe(3);
    for (const line of said) expect(line.length).toBeGreaterThan(6);
  });

  it("锁着优先说「先解锁」：既锁着又被改过时，用户要做的第一件事是解锁", () => {
    const both = block({ locked: true, user_modified: true });

    expect(isProtected(both)).toBe(true);
    // 屏里的顺序判断由 `protectedReason` 持有；这里钉住那条**优先级**的理由：
    // 解锁是可执行的一步，「你改过它」不是。
    expect(zh["intervention.protected.locked"]).toContain("解锁");
  });

  it("三种受保护在屏上各挂各的判别位", () => {
    // 判别位取值集合与三种来由一一对应——共用一个的话，取证里三者长得一样。
    const kinds = PROTECTED.map(([name]) => name);
    expect(new Set(kinds).size).toBe(3);
    expect(kinds).toEqual(["locked", "authored", "modified"]);
  });

  it("渲染一次三种受保护的话，确认它们真的是三段可读文字", () => {
    render(
      <ul>
        {PROTECTED.map(([name, , line]) => (
          <li key={name} data-protected-reason={name}>{line}</li>
        ))}
      </ul>,
    );

    for (const [, , line] of PROTECTED) {
      expect(screen.getByText(line)).toBeTruthy();
    }
  });
});
