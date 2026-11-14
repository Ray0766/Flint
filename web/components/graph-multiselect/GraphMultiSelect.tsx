// GRAPH-09：框选 + ⌘A + 批量设角色（F11）。
//
// **批量是另一条路**：主唯一在单个路径上（GRAPH-06）已经守住了，但一次选中八个节点
// 点「设为主」，很容易实现成「给八个都打上 primary」。那之后图里有八个主，
// I12-1 破了，而界面上看不出来——每个节点都显示自己是主。
//
// 所以这里做两件事：批量**一次请求**把整份选中项交给服务端（服务端在临界区里定主，
// 见 flint/graph/roles.py），前端**只呈现回值**——NEVER 自己挑「最后一个」当主。
// 前端挑的那个与服务端定的那个只要有一次不一致，用户看到的就是错的。
//
// 选择本身两条纪律：
// - 框选是**加选**不是替换：替换的话用户第二次框选就丢了第一次的，而他多半是想凑一批；
// - ⌘A 只选**画布内**的节点：把不在图里的东西也选上，随后的批量操作会作用到
//   用户根本没看见的对象上。

import type { JSX } from "react";
import { useEffect, useState } from "react";

import { t } from "../../lib/i18n/t";
import { pushUndo } from "../../lib/undo/undoStack";

export type NodeBox = { nodeId: string; x: number; y: number };
export type BatchRole = "primary" | "secondary" | "auxiliary";
export type BatchRoleResult = { primaryNodeId: string | null };
/** 操作前每个节点各自的角色。`null` = 那时它没有角色。 */
export type RoleSnapshot = { nodeId: string; role: BatchRole | null }[];

export type GraphMultiSelectProps = {
  nodes: NodeBox[];
  onBatchRole: (nodeIds: string[], role: BatchRole) => Promise<BatchRoleResult>;
  /**
   * 每个节点当前的角色。**给了才可能撤销**——撤销要把角色放回操作前那一个，
   * 而这个组件自己不知道操作前是什么（角色由服务端定，它只呈现回值）。
   */
  roles?: Record<string, BatchRole | null>;
  /** 把快照里的角色还原回去。与 `roles` 成对，缺一就不入栈。 */
  onRestoreRoles?: (snapshot: RoleSnapshot) => Promise<void>;
};

export function GraphMultiSelect({
  nodes,
  onBatchRole,
  roles,
  onRestoreRoles,
}: GraphMultiSelectProps): JSX.Element {
  const [selected, setSelected] = useState<string[]>([]);
  const [primaryNodeId, setPrimaryNodeId] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [origin, setOrigin] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const onKey = (event: KeyboardEvent): void => {
      if (event.key === "a" && (event.metaKey || event.ctrlKey)) {
        setSelected(nodes.map((n) => n.nodeId));       // 只选画布内的
        return;
      }
      if (event.key === "Escape") setSelected([]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [nodes]);

  const finishMarquee = (x2: number, y2: number): void => {
    if (origin === null) return;
    const [left, right] = [Math.min(origin.x, x2), Math.max(origin.x, x2)];
    const [top, bottom] = [Math.min(origin.y, y2), Math.max(origin.y, y2)];
    const hit = nodes
      .filter((n) => n.x >= left && n.x <= right && n.y >= top && n.y <= bottom)
      .map((n) => n.nodeId);
    setOrigin(null);
    setSelected((prev) => {                            // 加选：保留上一批
      const merged = [...prev, ...hit.filter((id) => !prev.includes(id))];
      return nodes.map((n) => n.nodeId).filter((id) => merged.includes(id));
    });
  };

  const applyRole = (role: BatchRole): void => {
    if (selected.length === 0) return;                 // 空批量没有语义
    // 快照要在**请求发出前**取：回来之后 roles 可能已经是新值了。
    const snapshot: RoleSnapshot | null =
      roles === undefined
        ? null
        : selected.map((nodeId) => ({ nodeId, role: roles[nodeId] ?? null }));
    void onBatchRole(selected, role)
      .then((result) => {
        setFailed(false);
        setPrimaryNodeId(result.primaryNodeId);        // 主由服务端定
        // 拿不到操作前的角色就 NEVER 入栈：**不造一个假的还原点**。
        // 假还原点比没有更糟——用户以为撤回去了，其实角色被改成了另一个值。
        if (snapshot === null || onRestoreRoles === undefined) return;
        pushUndo({
          view: "graph",
          label: "batch-role",
          undo: () => onRestoreRoles(snapshot),
        });
      })
      .catch(() => {
        setFailed(true);
      });
  };

  return (
    <div data-testid="graph-multiselect">
      <div
        data-testid="graph-multiselect-canvas"
        onPointerDown={(e) => setOrigin({ x: e.clientX, y: e.clientY })}
        onPointerUp={(e) => finishMarquee(e.clientX, e.clientY)}
      >
        {nodes.map((n) => (
          <span
            key={n.nodeId}
            data-testid="graph-multiselect-node"
            data-node-id={n.nodeId}
            data-selected={String(selected.includes(n.nodeId))}
            data-primary={String(primaryNodeId === n.nodeId)}
          />
        ))}
      </div>
      <div data-testid="graph-selection" data-selected={selected.join(",")} />
      <div
        data-testid="graph-multiselect-primary"
        data-primary-node-id={primaryNodeId ?? ""}
      />
      <button
        type="button"
        data-testid="graph-batch-primary"
        onClick={() => applyRole("primary")}
      >
        {t("graph.batch.primary")}
      </button>
      <button
        type="button"
        data-testid="graph-batch-secondary"
        onClick={() => applyRole("secondary")}
      >
        {t("graph.batch.secondary")}
      </button>
      {failed ? (
        <p data-testid="graph-multiselect-error">{t("graph.batch.failed")}</p>
      ) : null}
    </div>
  );
}
