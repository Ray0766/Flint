// GRAPH-04：节点拖动（rAF 节流 + 松手落盘 + 失败回弹）。
//
// 拖动期**零写请求**：每移动一像素发一次 PATCH，会把一次拖动变成上百次写，
// 而其中 99 次的位置用户根本没打算保留。
//
// 松手**恰一次** PATCH；失败**回弹原位**——不回弹的话，界面上节点停在新位置、
// 服务端还在老位置，下次刷新它自己跳回去，用户会以为是 bug 或数据丢了。

import type { JSX } from "react";
import { useRef, useState } from "react";

import { pushUndo } from "../../lib/undo/undoStack";

export type Point = { x: number; y: number };

export type GraphDragProps = {
  nodeId: string;
  initial: Point;
  /** 落盘；由上层注入（组件不发请求）。抛错 = 失败。 */
  persist: (nodeId: string, at: Point) => Promise<void>;
  /** 注入 rAF，便于测试驱动；默认用浏览器的。 */
  raf?: (cb: () => void) => number;
};

export function GraphDrag({ nodeId, initial, persist, raf }: GraphDragProps): JSX.Element {
  const [at, setAt] = useState<Point>(initial);
  const [dragging, setDragging] = useState(false);
  const origin = useRef<Point>(initial);
  const pendingFrame = useRef<number | null>(null);
  const schedule = raf ?? ((cb: () => void) => window.requestAnimationFrame(cb));

  const onDown = () => {
    origin.current = at;                 // 记住原位，失败时回弹用
    setDragging(true);
  };

  const onMove = (next: Point) => {
    if (!dragging) return;
    // rAF 节流：一帧内的多次移动合并成一次渲染；**期间不发任何请求**
    if (pendingFrame.current !== null) return;
    pendingFrame.current = schedule(() => {
      pendingFrame.current = null;
      setAt(next);
    });
  };

  const onUp = (final: Point) => {
    if (!dragging) return;
    setDragging(false);
    setAt(final);
    const before = origin.current;
    void persist(nodeId, final).then(
      () => {
        // 落盘**成功**才入栈：失败的那一次已经回弹，没有东西要撤。
        // 位置没变也不入栈——空操作入栈会让 ⌘Z 看起来失灵（按一下什么都没发生）。
        if (before.x === final.x && before.y === final.y) return;
        pushUndo({
          view: "graph",
          label: "move-node",
          // 先落盘再改界面：反过来的话落盘失败时界面已经跳回去了，
          // 而服务端还在新位置——下次刷新它又跳一次。
          undo: async () => {
            await persist(nodeId, before);
            setAt(before);
          },
        });
      },
      () => {
        setAt(before);                   // 失败回弹原位
      },
    );
  };

  return (
    <g
      data-testid="graph-drag"
      data-node-id={nodeId}
      data-x={at.x}
      data-y={at.y}
      data-dragging={String(dragging)}
      onPointerDown={onDown}
      onPointerMove={(e) => onMove({ x: e.clientX, y: e.clientY })}
      onPointerUp={(e) => onUp({ x: e.clientX, y: e.clientY })}
    />
  );
}
