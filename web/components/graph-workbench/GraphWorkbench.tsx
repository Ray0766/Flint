import { useState, type JSX } from "react";

import { GenerateGate, type GraphEdgeView } from "../graph-generate-gate/GenerateGate";
import { GraphNode } from "../graph-node/GraphNode";
import { NotProvided } from "../shell/NotProvided";
import { t } from "../../lib/i18n/t";

/**
 * UI-03 / v2 屏 2.16：热点工作台·图谱的**画布装配层**。
 *
 * GRAPH 组 16 卡把节点、连线、角色、多选、生成闸门、拖拽、撤销都做好了，
 * 但它们至今**没有一块画布把它们摆在一起**。本组件只做装配与取数，
 * 一条交互逻辑都不重写——重写就等于同一件事有了两个实现，而它们会各自漂移。
 *
 * ## 三态里最要紧的一条：「没查过」不是「空图」
 *
 * `GET /workbenches`【未建·接口预留】（`docs/前端功能说明-v2.md#2.16`）。
 * 所以 `graph == null` 的意思是**我们根本没查过这张图**，它渲染成「接口未提供」。
 *
 * v2 那条「空图 → 引导『从广场拖入第一个热点』」说的是**查过了、确实是空的**。
 * 端点没建就把空图引导画出来，等于告诉用户「你的工作台是空的」——
 * 而真相是我们不知道。这是本轮反复出现的同一条（`not_checked` ≠ `checked-empty`）。
 *
 * ## 空图 NEVER 预置示例节点
 *
 * v2 原话。预置的节点与用户自己拖进来的长得一样，他会以为那是他的东西。
 *
 * ## 移动端只读（E10）
 *
 * 只读时增删改控件**不渲染**（不是置灰）——与保护块那条纪律同源：
 * 置灰的控件仍然告诉用户「这里本来能点」，而在只读端它永远不能点。
 */

export type WorkbenchNode = {
  nodeId: string;
  sourceKind: "cluster" | "evidence_card" | "topic";
  nameNative: string;
  primary?: boolean;
};

export type WorkbenchGraph = {
  nodes: WorkbenchNode[];
  edges: GraphEdgeView[];
  /** 图内 primary（I12-1 恒 ≤1）；没有就是 null，**NEVER 由前端挑一个**。 */
  primaryNodeId: string | null;
};

export type GraphWorkbenchProps = {
  /** `null` = 没查过（端点未建）。`{nodes: []}` = 查过了、空图。**两者不是一回事**。 */
  graph: WorkbenchGraph | null;
  /** 移动端只读（E10）：可看可缩放，不提供增删改控件。 */
  readOnly?: boolean;
  onGenerate?: () => void;
  onLocateEdges?: (edgeIds: string[]) => void;
  /** `EDGES-UI`：连线。**不传就不渲染那个表单**——
   *  渲染一个按不动的按钮，与「这个能力没有」在屏上长得一样。 */
  onConnect?: (from: string, to: string, hypothesis: string) => void;
  /** 上一次连线的结果。`null` = 还没连过。 */
  connectState?: { phase: "working" | "error"; message?: string } | null;
};

export function GraphWorkbench({
  graph,
  readOnly = false,
  onGenerate,
  onLocateEdges,
  onConnect,
  connectState = null,
}: GraphWorkbenchProps): JSX.Element {
  // 连线的两端与那句假设。**假设是必填**——一条没有假设的边说不出
  // 两端为什么被连起来（冻结件 `GraphEdge` 逐字拒空）。
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [hypothesis, setHypothesis] = useState("");
  if (graph === null) {
    // 没查过。**不画空图引导**——那句话说的是「查过了、是空的」。
    return (
      <section className="workbench" data-workbench-state="not_provided">
        <NotProvided label={t("workbench.graph.not_provided")} />
        <p className="workbench__hint">{t("workbench.graph.not_provided_hint")}</p>
      </section>
    );
  }

  if (graph.nodes.length === 0) {
    // 查过了、确实是空的。引导用户自己拖第一个进来，**NEVER 预置示例节点**。
    return (
      <section className="workbench" data-workbench-state="empty">
        <p className="workbench__empty">{t("workbench.graph.empty")}</p>
      </section>
    );
  }

  return (
    <section className="workbench" data-workbench-state="ready">
      <ol className="workbench__canvas" aria-label={t("workbench.graph.canvas")}>
        {graph.nodes.map((node) => (
          <li key={node.nodeId} className="workbench__node">
            <GraphNode
              nodeId={node.nodeId}
              sourceKind={node.sourceKind}
              primary={node.primary}
              nameNative={node.nameNative}
            />
          </li>
        ))}
      </ol>
      {readOnly ? null : (
        // 只读端**根本不渲染**这些控件（E10）。
        <div className="workbench__actions" data-workbench-actions="true">
          <GenerateGate
            edges={graph.edges}
            primaryNodeId={graph.primaryNodeId}
            onGenerate={onGenerate ?? (() => undefined)}
            onLocate={onLocateEdges}
          />
          {onConnect ? (
            <form
              className="workbench__connect"
              data-workbench-connect="true"
              onSubmit={(event) => {
                event.preventDefault();
                onConnect(from, to, hypothesis);
              }}
            >
              <select
                data-connect-from
                value={from}
                onChange={(e) => setFrom(e.target.value)}
              >
                <option value="">{t("workbench.connect.from")}</option>
                {graph.nodes.map((n) => (
                  <option key={n.nodeId} value={n.nodeId}>{n.nameNative}</option>
                ))}
              </select>
              <select
                data-connect-to
                value={to}
                onChange={(e) => setTo(e.target.value)}
              >
                <option value="">{t("workbench.connect.to")}</option>
                {graph.nodes.map((n) => (
                  <option key={n.nodeId} value={n.nodeId}>{n.nameNative}</option>
                ))}
              </select>
              <input
                data-connect-hypothesis
                value={hypothesis}
                placeholder={t("workbench.connect.hypothesis")}
                onChange={(e) => setHypothesis(e.target.value)}
              />
              <button
                type="submit"
                data-connect-submit
                disabled={connectState?.phase === "working"}
              >
                {t("workbench.connect.submit")}
              </button>
              {connectState?.phase === "error" ? (
                // 存不下就**说存不下**，NEVER 把线留在画布上假装成功。
                <span className="workbench__connect-error" data-connect-error>
                  {connectState.message}
                </span>
              ) : null}
            </form>
          ) : null}
        </div>
      )}
    </section>
  );
}
