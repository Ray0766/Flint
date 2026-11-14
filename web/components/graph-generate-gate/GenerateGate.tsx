// GRAPH-08：空假设阻断生成 + AI 栏摘要条（F9/F10）。
//
// **置灰之外必须给计数和定位**：一个灰着的按钮只说明「不能生成」，不说明
// 「缺什么、在哪」。用户面对一张十几个节点的图会挨个点开每条边去找——
// 那正是系统已经知道答案却不肯说的时候。所以徽章报出条数，点它把缺假设的边
// 逐条交给调用方去高亮。
//
// **闸门自己看数据**：GRAPH-07 之后新建的边不可能空假设（前后端各拦一道），
// 但这道闸挡的是别的来路——早于该规则入库的边、批量导入、以及将来任何绕过 UI 的写入。
// 所以 props 面不收 `hasEmptyHypothesis` 这类由调用方给的结论：一旦收了，
// 闸门的正确性就取决于每一个调用点都算对了，而那是没法验的。
//
// **摘要条三项**（primary / 边数 / 假设完整度）都挂成 data 属性：它们是给人看的，
// 也是上层与测试能读回的事实。没有 primary 时如实空着——挑一个节点冒充主，
// 等于替用户回答「这张图在讲哪件事」。
//
// **空图不谎报完整**：零条边时完整度是 0/0。按钮同样不可点，但理由不是缺假设，
// 所以那种情况下 NEVER 出缺假设徽章（否则用户会去找一条并不存在的坏边）。

import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

export type GraphEdgeView = {
  edgeId: string;
  fromNodeId: string;
  toNodeId: string;
  hypothesis: string;
};

export type GenerateGateProps = {
  edges: GraphEdgeView[];
  /** 图内 primary（I12-1 恒 ≤1）；没有就是 null，NEVER 由本组件挑一个 */
  primaryNodeId: string | null;
  onGenerate: () => void;
  /** 把缺假设的边交出去高亮定位 */
  onLocate?: (edgeIds: string[]) => void;
};

export function GenerateGate({
  edges,
  primaryNodeId,
  onGenerate,
  onLocate,
}: GenerateGateProps): JSX.Element {
  const missing = edges.filter((e) => e.hypothesis.trim() === "");
  const complete = edges.length - missing.length;
  const blocked = missing.length > 0 || edges.length === 0;

  return (
    <div data-testid="graph-generate-gate">
      <div
        data-testid="graph-summary-bar"
        data-primary-node-id={primaryNodeId ?? ""}
        data-edge-count={edges.length}
        data-hypothesis-complete={complete}
        data-hypothesis-total={edges.length}
      >
        <span data-testid="graph-summary-primary">
          {primaryNodeId === null
            ? t("graph.summary.no_primary")
            : t("graph.summary.primary", { node: primaryNodeId })}
        </span>
        <span data-testid="graph-summary-edges">
          {t("graph.summary.edges", { count: edges.length })}
        </span>
        <span data-testid="graph-summary-hypotheses">
          {t("graph.summary.hypotheses", { complete, total: edges.length })}
        </span>
      </div>
      {missing.length > 0 ? (
        <button
          type="button"
          data-testid="generate-gate-badge"
          data-count={missing.length}
          onClick={() => onLocate?.(missing.map((e) => e.edgeId))}
        >
          {t("graph.gate.missing_hypotheses", { count: missing.length })}
        </button>
      ) : null}
      <button
        type="button"
        data-testid="generate-button"
        disabled={blocked}
        onClick={() => onGenerate()}
      >
        {t("graph.gate.generate")}
      </button>
    </div>
  );
}
