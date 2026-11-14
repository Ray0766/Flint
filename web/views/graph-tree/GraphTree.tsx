// GRAPH-12：树视图 = primary 为根的 BFS 投影 + 未连接区（F13/F14）。
//
// 图与树是**同一份数据的两种画法**，不是两份数据。切一下视图少了两个节点，
// 用户不会想到「那是投影规则的问题」——他会以为自己把它们删了，
// 然后回到图谱里去找那两个再也找不到的东西。所以投影的硬约束是：
// **树里的节点 + 未连接区 = 图里的全部节点**，一个不多一个不少。
//
// ## 未连接区是个如实的去处
//
// 从 primary 出发走不到的节点**不挂到根下面充数**：挂上去等于凭空发明一条关系，
// 而这张图里的每条边都要有假设（GRAPH-07）。它们进「未连接」区，
// 用户一眼看见「这几个还没接进来」——那正是他下一步要做的事。
//
// ## 没有 primary 就没有树
//
// 不挑一个节点当根：那等于替用户回答「这张图在讲哪件事」（与 GRAPH-06/08 同一条纪律）。
// 此时全部节点进未连接区——**如实**，而不是画一棵以任意节点为根的假树。
//
// ## 有向
//
// 边有方向（I8），BFS 只沿 from → to 走。反向边不把父子关系倒过来：
// 倒过来的话，「A 导致 B」会在树上显示成「B 之下有 A」。

import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

export type TreeNode = { nodeId: string; label: string; primary: boolean };
export type TreeEdge = { fromNodeId: string; toNodeId: string; hypothesis: string };

export type TreeProjection = {
  rootId: string | null;
  /** 节点 → 距根层数；不在树里的节点不出现在这里 */
  depthOf: Record<string, number>;
  /** 父 → 子（同层按 id 稳定排序，刷新不换位置） */
  childrenOf: Record<string, string[]>;
  /** 从根走不到的节点 */
  detachedIds: string[];
};

export function projectToTree(nodes: TreeNode[], edges: TreeEdge[]): TreeProjection {
  const known = new Set(nodes.map((n) => n.nodeId));
  const outgoing: Record<string, string[]> = {};
  for (const edge of edges) {
    if (!known.has(edge.fromNodeId) || !known.has(edge.toNodeId)) continue;
    outgoing[edge.fromNodeId] = [...(outgoing[edge.fromNodeId] ?? []), edge.toNodeId];
  }
  for (const from of Object.keys(outgoing)) {
    outgoing[from] = [...outgoing[from]].sort();      // 稳定：刷新不换位置
  }

  const root = nodes.find((n) => n.primary) ?? null;
  const depthOf: Record<string, number> = {};
  const childrenOf: Record<string, string[]> = {};

  if (root !== null) {
    depthOf[root.nodeId] = 0;
    const queue = [root.nodeId];
    while (queue.length > 0) {
      const current = queue.shift() as string;
      const children: string[] = [];
      for (const next of outgoing[current] ?? []) {
        if (depthOf[next] !== undefined) continue;    // 环：只落一层，不再回头
        depthOf[next] = depthOf[current] + 1;
        children.push(next);
        queue.push(next);
      }
      childrenOf[current] = children;
    }
  }

  const detachedIds = nodes
    .map((n) => n.nodeId)
    .filter((id) => depthOf[id] === undefined)
    .sort();

  return { rootId: root?.nodeId ?? null, depthOf, childrenOf, detachedIds };
}

export function GraphTree({
  nodes,
  edges,
}: {
  nodes: TreeNode[];
  edges: TreeEdge[];
}): JSX.Element {
  const tree = projectToTree(nodes, edges);
  const labelOf = new Map(nodes.map((n) => [n.nodeId, n.label]));
  const inTree = Object.keys(tree.depthOf).sort(
    (a, b) => tree.depthOf[a] - tree.depthOf[b] || a.localeCompare(b),
  );

  return (
    <section data-testid="graph-tree" data-node-count={nodes.length}>
      <ul>
        {inTree.map((id) => (
          <li
            key={id}
            data-testid="graph-tree-node"
            data-node-id={id}
            data-depth={tree.depthOf[id]}
          >
            {labelOf.get(id)}
          </li>
        ))}
      </ul>
      <div data-testid="graph-tree-detached">
        <h3>{t("graph.tree.detached")}</h3>
        <ul>
          {tree.detachedIds.map((id) => (
            <li key={id} data-testid="graph-tree-detached-node" data-node-id={id}>
              {labelOf.get(id)}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
