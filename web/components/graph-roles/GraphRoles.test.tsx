// GRAPH-06 验收（前端半）：角色菜单 + 旧主降级 toast（NEVER 确认对话框）。
//
// acceptance①「设第二主 → 旧主自动降 secondary + toast（NEVER 确认对话框）」。
//
// 为什么不弹确认框：用户点第二个节点设主，意思已经很明确；再问一句
// 「确定要替换吗」是把系统的洁癖变成用户的负担。但降级**必须如实告诉他**——
// 悄悄换掉主而不吭声，他下次看这张图时会以为自己记错了。
//
// 降级是**服务端算的**（flint/graph/roles.py 在临界区内定的）。前端只呈现回值，
// NEVER 自己推断谁被降了：本地推断在并发下必然与服务端不一致，而用户看到的
// 是本地那份。
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { GraphRoles } from "./GraphRoles";

const SOURCE = readFileSync(join(__dirname, "GraphRoles.tsx"), "utf8");

describe("GraphRoles（角色菜单）", () => {
  it("三个角色项都在，点主调服务端恰一次", async () => {
    const setRole = vi.fn().mockResolvedValue({ demotedNodeId: null });
    render(<GraphRoles nodeId="n-1" onSetRole={setRole} />);

    expect(screen.getAllByRole("menuitem")).toHaveLength(3);
    fireEvent.click(screen.getByTestId("graph-role-primary"));

    await waitFor(() => expect(setRole).toHaveBeenCalledTimes(1));
    expect(setRole).toHaveBeenCalledWith("n-1", "primary");
  });

  it("旧主被降级 → 出 toast 并点名是谁；NEVER 弹确认对话框", async () => {
    const confirmSpy = vi.spyOn(window, "confirm");
    const setRole = vi.fn().mockResolvedValue({ demotedNodeId: "n-0" });
    render(<GraphRoles nodeId="n-1" onSetRole={setRole} />);

    fireEvent.click(screen.getByTestId("graph-role-primary"));

    const toast = await screen.findByTestId("graph-role-toast");
    expect(toast).toHaveAttribute("data-demoted-node-id", "n-0");
    expect(toast.textContent).toBeTruthy();
    expect(confirmSpy).not.toHaveBeenCalled();
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(screen.queryByRole("dialog")).toBeNull();
    confirmSpy.mockRestore();
  });

  it("没有谁被降级就不出 toast：NEVER 报一个自己降了自己的提示", async () => {
    const setRole = vi.fn().mockResolvedValue({ demotedNodeId: null });
    render(<GraphRoles nodeId="n-1" onSetRole={setRole} />);

    fireEvent.click(screen.getByTestId("graph-role-primary"));

    await waitFor(() => expect(setRole).toHaveBeenCalled());
    expect(screen.queryByTestId("graph-role-toast")).toBeNull();
  });

  it("降级与否只看服务端回值：本地看起来该降也不擅自报", async () => {
    // 服务端说没人被降（并发下它才是权威），前端就不该凭「刚才那个是主」自己补一条
    const setRole = vi.fn().mockResolvedValue({ demotedNodeId: null });
    render(<GraphRoles nodeId="n-1" currentPrimaryId="n-0" onSetRole={setRole} />);

    fireEvent.click(screen.getByTestId("graph-role-primary"));

    await waitFor(() => expect(setRole).toHaveBeenCalled());
    expect(screen.queryByTestId("graph-role-toast")).toBeNull();
  });

  it("设次要/辅助也走同一条路，且不产生降级提示", async () => {
    const setRole = vi.fn().mockResolvedValue({ demotedNodeId: null });
    render(<GraphRoles nodeId="n-1" onSetRole={setRole} />);

    fireEvent.click(screen.getByTestId("graph-role-secondary"));
    await waitFor(() => expect(setRole).toHaveBeenCalledWith("n-1", "secondary"));

    fireEvent.click(screen.getByTestId("graph-role-auxiliary"));
    await waitFor(() => expect(setRole).toHaveBeenCalledWith("n-1", "auxiliary"));
    expect(screen.queryByTestId("graph-role-toast")).toBeNull();
  });

  it("设主失败不谎报成功：出错误态，且没有 toast", async () => {
    const setRole = vi.fn().mockRejectedValue(new Error("boom"));
    render(<GraphRoles nodeId="n-1" onSetRole={setRole} />);

    fireEvent.click(screen.getByTestId("graph-role-primary"));

    await screen.findByTestId("graph-role-error");
    expect(screen.queryByTestId("graph-role-toast")).toBeNull();
  });

  it("角色集恰是三项，与契约 NodeRole 同集", () => {
    render(
      <GraphRoles nodeId="n-1" onSetRole={vi.fn().mockResolvedValue({ demotedNodeId: null })} />,
    );
    expect(
      screen.getAllByRole("menuitem").map((n) => n.getAttribute("data-role")),
    ).toEqual(["primary", "secondary", "auxiliary"]);
  });

  it("源码里没有确认对话框、也没有本地降级推断", () => {
    for (const forbidden of ["window.confirm", "confirm(", "alertdialog"]) {
      expect(SOURCE).not.toContain(forbidden);
    }
    // 本地推断的形态：拿 currentPrimaryId 去和 nodeId 比，然后自己判谁被降
    expect(SOURCE).not.toMatch(/currentPrimaryId\s*(!==|===)/);
  });

  it("文案 key 化：源码代码行零 CJK", () => {
    const code = SOURCE.replace(/\/\*[\s\S]*?\*\//g, "")
      .split("\n")
      .filter((l) => !l.trim().startsWith("//"))
      .join("\n");
    expect(code).not.toMatch(/[一-鿿]/);
  });
});
