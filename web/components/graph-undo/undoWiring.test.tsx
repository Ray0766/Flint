// DEF-03 验收：undo 链三处接线（GRAPH-04 拖动 / GRAPH-07 连线 / GRAPH-09 批量角色）。
//
// ## 卡面与实况的差
//
// 卡面说「三处操作点留了 pushUndo 调用位」。实况是三个组件里**零处**提到 undo——
// 留下的缝是另一样东西：三处的写操作都是**注入**的（persist / onCreate / onBatchRole），
// 所以撤销动作能用同一个注入件反着做一次。本卡按真件接线。
//
// ## 撤销要能真的撤回去，否则 NEVER 入栈
//
// 三处的入栈条件各不相同，但理由是同一条：**能入栈就等于向用户承诺这一步撤得掉**。
// 撤不掉却入了栈，用户按 ⌘Z 会看到「撤销失败」，而他此刻已经不记得那步是什么了。
//
// - 拖动：落盘**成功**才入栈（失败的那次已经回弹，没有东西要撤）；位置没变也不入栈
//   （空操作入栈会让 ⌘Z 看起来失灵——按一下什么都没发生）。
// - 连线：没给撤销回调就不入栈（删不掉的边，撤销只能失败）。
// - 批量角色：拿不到操作前的角色就不入栈（**NEVER 造一个假的还原点**）。
//
// ## 只回退该操作
//
// 一条链跨视图（§6-H5），所以「撤最近一步」必须**只**动那一步碰过的东西。
// 相邻状态逐字节不变——差一个像素，用户就会发现自己的另一处编辑被顺手改了。
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GraphDrag } from "../graph-drag/GraphDrag";
import { GraphEdgeDraft } from "../graph-edge/GraphEdgeDraft";
import { GraphMultiSelect } from "../graph-multiselect/GraphMultiSelect";
import type { Block, BlockContent } from "../../lib/types";
import {
  clearUndo,
  getUndoStack,
  pushBlockUndo,
  undo,
  undoDepth,
} from "../../lib/undo/undoStack";

const syncRaf = (cb: () => void) => {
  cb();
  return 1;
};

function block(over: Partial<Block> = {}): Block {
  const content: BlockContent = { kind: "paragraph", spans: [{ kind: "text", text: "正文" }] };
  return {
    block_id: "b-1", deliverable_id: "d-1", section_id: "s-1", order: 0,
    type: content.kind, content, claim_ids: [], fact_ids: [],
    author: "system", revision: 1, locked: false, user_modified: false,
    needs_review: false, review_reason: null, review_severity: null, ...over,
  };
}

function dragTo(node: HTMLElement, x: number, y: number): void {
  fireEvent.pointerDown(node, { clientX: 10, clientY: 20 });
  fireEvent.pointerMove(node, { clientX: x, clientY: y });
  fireEvent.pointerUp(node, { clientX: x, clientY: y });
}

beforeEach(() => {
  clearUndo();
});

describe("GRAPH-04 拖动接进 undo 链", () => {
  it("落盘成功后入栈一条，撤销把节点放回原位并落盘", async () => {
    const persist = vi.fn(async () => {});
    render(
      <svg>
        <GraphDrag nodeId="n-1" initial={{ x: 10, y: 20 }} persist={persist} raf={syncRaf} />
      </svg>,
    );
    const node = screen.getByTestId("graph-drag");

    dragTo(node, 90, 80);
    await waitFor(() => expect(undoDepth()).toBe(1));
    expect(node.getAttribute("data-x")).toBe("90");

    const entry = getUndoStack()[0];
    expect(entry?.view).toBe("graph");
    expect(entry?.label).toBe("move-node");

    await undo();

    await waitFor(() => expect(node.getAttribute("data-x")).toBe("10"));
    expect(node.getAttribute("data-y")).toBe("20");
    // 撤销也要落盘：只改界面的话，刷新一下节点又跳回去了
    expect(persist).toHaveBeenLastCalledWith("n-1", { x: 10, y: 20 });
    expect(undoDepth()).toBe(0);
  });

  it("落盘失败 NEVER 入栈——那一步根本没发生过", async () => {
    const persist = vi.fn(async () => {
      throw new Error("网络错误");
    });
    render(
      <svg>
        <GraphDrag nodeId="n-1" initial={{ x: 10, y: 20 }} persist={persist} raf={syncRaf} />
      </svg>,
    );

    dragTo(screen.getByTestId("graph-drag"), 90, 80);

    await waitFor(() => expect(screen.getByTestId("graph-drag").getAttribute("data-x")).toBe("10"));
    expect(undoDepth()).toBe(0);
  });

  it("位置没变不入栈——空操作入栈会让 ⌘Z 看起来失灵", async () => {
    const persist = vi.fn(async () => {});
    render(
      <svg>
        <GraphDrag nodeId="n-1" initial={{ x: 10, y: 20 }} persist={persist} raf={syncRaf} />
      </svg>,
    );

    dragTo(screen.getByTestId("graph-drag"), 10, 20);

    await waitFor(() => expect(persist).toHaveBeenCalledTimes(1));
    expect(undoDepth()).toBe(0);
  });
});

describe("GRAPH-07 连线接进 undo 链", () => {
  function setup(onUndoCreate?: (p: unknown) => Promise<void>) {
    const onCreate = vi.fn(async () => ({ edge_id: "e-1" }));
    render(
      <GraphEdgeDraft
        fromNodeId="n-1"
        toNodeId="n-2"
        onCreate={onCreate}
        onUndoCreate={onUndoCreate}
      />,
    );
    fireEvent.change(screen.getByTestId("graph-edge-hypothesis-input"), {
      target: { value: "A 带动 B" },
    });
    fireEvent.click(screen.getByTestId("graph-edge-submit"));
    return { onCreate };
  }

  it("建边成功后入栈一条，撤销把这条边删掉", async () => {
    const onUndoCreate = vi.fn(async () => {});
    setup(onUndoCreate);

    await waitFor(() => expect(undoDepth()).toBe(1));
    expect(getUndoStack()[0]?.label).toBe("add-edge");

    await undo();

    expect(onUndoCreate).toHaveBeenCalledWith({
      fromNodeId: "n-1",
      toNodeId: "n-2",
      hypothesis: "A 带动 B",
    });
    expect(undoDepth()).toBe(0);
  });

  it("没给撤销回调就 NEVER 入栈——删不掉的边，撤销只能失败", async () => {
    const { onCreate } = setup(undefined);

    await waitFor(() => expect(onCreate).toHaveBeenCalledTimes(1));
    expect(undoDepth()).toBe(0);
  });

  it("空假设本地拦下时不入栈（连请求都没发，更没有东西要撤）", () => {
    render(
      <GraphEdgeDraft
        fromNodeId="n-1"
        toNodeId="n-2"
        onCreate={vi.fn(async () => ({}))}
        onUndoCreate={vi.fn(async () => {})}
      />,
    );

    fireEvent.click(screen.getByTestId("graph-edge-submit"));

    expect(screen.getByTestId("graph-edge-hypothesis-required")).toBeTruthy();
    expect(undoDepth()).toBe(0);
  });
});

describe("GRAPH-09 批量角色接进 undo 链", () => {
  const nodes = [
    { nodeId: "n-1", x: 10, y: 10 },
    { nodeId: "n-2", x: 20, y: 20 },
  ];

  function setup(withRestore: boolean) {
    const onBatchRole = vi.fn(async () => ({ primaryNodeId: "n-1" }));
    const onRestoreRoles = vi.fn(async () => {});
    render(
      <GraphMultiSelect
        nodes={nodes}
        onBatchRole={onBatchRole}
        roles={withRestore ? { "n-1": "secondary", "n-2": null } : undefined}
        onRestoreRoles={withRestore ? onRestoreRoles : undefined}
      />,
    );
    fireEvent.keyDown(window, { key: "a", metaKey: true });
    fireEvent.click(screen.getByTestId("graph-batch-primary"));
    return { onBatchRole, onRestoreRoles };
  }

  it("批量成功后入栈一条，撤销把每个节点的角色放回操作前那一个", async () => {
    const { onRestoreRoles } = setup(true);

    await waitFor(() => expect(undoDepth()).toBe(1));
    expect(getUndoStack()[0]?.label).toBe("batch-role");

    await undo();

    // 快照是**操作前**的角色，逐个节点各自的那一个——NEVER 一律回退成 null
    expect(onRestoreRoles).toHaveBeenCalledWith([
      { nodeId: "n-1", role: "secondary" },
      { nodeId: "n-2", role: null },
    ]);
    expect(undoDepth()).toBe(0);
  });

  it("只选中一部分时，快照里**只有**那一部分（只回退该操作）", async () => {
    // 这一条是变异考补上来的：把快照改成「取全部节点」时，上面那条 ⌘A 用例
    // **一条都不红**——⌘A 选中的正好是全部，两种写法在那份数据上一模一样。
    // 自洽不等于正确：用户框选 2 个节点却撤回 8 个，另外 6 个是这次操作
    // 从没碰过的，而 acceptance① 要的正是「只回退该操作」。
    const onRestoreRoles = vi.fn(async () => {});
    render(
      <GraphMultiSelect
        nodes={[
          { nodeId: "n-1", x: 10, y: 10 },
          { nodeId: "n-2", x: 20, y: 20 },
          { nodeId: "n-3", x: 500, y: 500 },
        ]}
        onBatchRole={vi.fn(async () => ({ primaryNodeId: "n-1" }))}
        roles={{ "n-1": "secondary", "n-2": null, "n-3": "auxiliary" }}
        onRestoreRoles={onRestoreRoles}
      />,
    );

    const canvas = screen.getByTestId("graph-multiselect-canvas");
    fireEvent.pointerDown(canvas, { clientX: 0, clientY: 0 });
    fireEvent.pointerUp(canvas, { clientX: 100, clientY: 100 });   // 框住 n-1 / n-2
    await waitFor(() =>
      expect(screen.getByTestId("graph-selection").getAttribute("data-selected")).toBe("n-1,n-2"),
    );

    fireEvent.click(screen.getByTestId("graph-batch-primary"));
    await waitFor(() => expect(undoDepth()).toBe(1));

    await undo();

    expect(onRestoreRoles).toHaveBeenCalledWith([
      { nodeId: "n-1", role: "secondary" },
      { nodeId: "n-2", role: null },
    ]);
  });

  it("拿不到操作前的角色就 NEVER 入栈——不造假的还原点", async () => {
    const { onBatchRole } = setup(false);

    await waitFor(() => expect(onBatchRole).toHaveBeenCalledTimes(1));
    expect(undoDepth()).toBe(0);
  });

  it("空选中不发请求也不入栈", () => {
    render(
      <GraphMultiSelect
        nodes={nodes}
        onBatchRole={vi.fn(async () => ({ primaryNodeId: null }))}
        roles={{ "n-1": null, "n-2": null }}
        onRestoreRoles={vi.fn(async () => {})}
      />,
    );

    fireEvent.click(screen.getByTestId("graph-batch-primary"));

    expect(undoDepth()).toBe(0);
  });
});

describe("S2-5：受保护 block 的操作 NEVER 进 undo 栈", () => {
  const entry = { view: "editor", label: "regenerate", undo: async () => {} };

  it("三种保护条件各自都挡住", () => {
    for (const over of [
      { locked: true },
      { author: "user" as const },
      { user_modified: true },
    ]) {
      clearUndo();

      expect(pushBlockUndo(block(over), entry)).toBe(false);
      expect(undoDepth()).toBe(0);
    }
  });

  it("没被保护的照常入栈（阴性对照：这道闸不是把所有 block 都挡了）", () => {
    expect(pushBlockUndo(block(), entry)).toBe(true);
    expect(undoDepth()).toBe(1);
  });

  it("入栈与否有返回值——NEVER 让调用方以为一定入了栈", () => {
    // 挡下的那一刻上游其实已经违规了（受保护 block 本来就改不动），
    // 返回值是调用方唯一能发现这件事的地方。
    expect(pushBlockUndo(block({ locked: true }), entry)).toBe(false);
    expect(pushBlockUndo(block(), entry)).toBe(true);
  });
});

describe("一条链：只回退该操作", () => {
  it("撤最近一步，相邻状态逐字节不变", async () => {
    const persist = vi.fn(async () => {});
    render(
      <svg>
        <GraphDrag nodeId="n-1" initial={{ x: 10, y: 20 }} persist={persist} raf={syncRaf} />
      </svg>,
    );
    const node = screen.getByTestId("graph-drag");

    dragTo(node, 90, 80);
    await waitFor(() => expect(undoDepth()).toBe(1));
    const afterFirst = node.outerHTML;

    fireEvent.pointerDown(node, { clientX: 90, clientY: 80 });
    fireEvent.pointerMove(node, { clientX: 150, clientY: 160 });
    fireEvent.pointerUp(node, { clientX: 150, clientY: 160 });
    await waitFor(() => expect(undoDepth()).toBe(2));

    await undo();

    // 第二步撤掉了；第一步留下的那份状态**逐字节**与撤销前相同
    await waitFor(() => expect(node.outerHTML).toBe(afterFirst));
    expect(undoDepth()).toBe(1);
  });

  it("跨视图共用同一条链：先拖动再连线，⌘Z 先撤连线", async () => {
    const persist = vi.fn(async () => {});
    const onUndoCreate = vi.fn(async () => {});
    render(
      <div>
        <svg>
          <GraphDrag nodeId="n-1" initial={{ x: 10, y: 20 }} persist={persist} raf={syncRaf} />
        </svg>
        <GraphEdgeDraft
          fromNodeId="n-1"
          toNodeId="n-2"
          onCreate={vi.fn(async () => ({}))}
          onUndoCreate={onUndoCreate}
        />
      </div>,
    );

    dragTo(screen.getByTestId("graph-drag"), 90, 80);
    await waitFor(() => expect(undoDepth()).toBe(1));

    fireEvent.change(screen.getByTestId("graph-edge-hypothesis-input"), {
      target: { value: "A 带动 B" },
    });
    fireEvent.click(screen.getByTestId("graph-edge-submit"));
    await waitFor(() => expect(undoDepth()).toBe(2));

    const popped = await undo();

    expect(popped?.label).toBe("add-edge");
    expect(onUndoCreate).toHaveBeenCalledTimes(1);
    // 拖动那一步一动没动：它还在栈上，节点也还在松手的位置
    expect(screen.getByTestId("graph-drag").getAttribute("data-x")).toBe("90");
    expect(undoDepth()).toBe(1);
  });
});
