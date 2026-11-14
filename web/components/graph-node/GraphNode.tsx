// GRAPH-03：图谱节点渲染（native 主行 + 辅助槽）。
//
// **复用不复制**：主行与机翻次要行走 NativeName（I18N-04-b），
// region/日期/stale/判定四个辅助槽走 HotspotCard 的同款槽位语义——
// 节点是「热点在画布上的投影」，两处若各写一套，同一个热点在广场与画布上
// 会显示出不同的东西。

import type { JSX } from "react";

import { HotspotCard, type HotspotCardProps } from "../hotspot-card/HotspotCard";

export type GraphNodeProps = HotspotCardProps & {
  nodeId: string;
  /** 节点投影的实体类别（cluster / evidence_card / topic）。 */
  sourceKind: "cluster" | "evidence_card" | "topic";
  /** 是否为该图的 primary（I12-1：图内恒 ≤1）。 */
  primary?: boolean;
};

export function GraphNode({
  nodeId,
  sourceKind,
  primary = false,
  ...card
}: GraphNodeProps): JSX.Element {
  return (
    <g
      className="graph-node"
      data-testid="graph-node"
      data-node-id={nodeId}
      data-source-kind={sourceKind}
      data-primary={String(primary)}
    >
      <foreignObject className="graph-node__body">
        <HotspotCard {...card} />
      </foreignObject>
    </g>
  );
}
