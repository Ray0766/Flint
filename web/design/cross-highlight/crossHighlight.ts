// DESIGN-26：反向高亮（G32，节点 ↔ 首个引用 Block）。
//
// **取「首个」而不是「全部」**：一个节点常被文书里好几处引用。一次把七处都高亮，
// 用户还是不知道该看哪；滚到第一处并高亮它，是一个明确的落点，他从那里往下读就行。
// 其余引用不是丢了——它们仍在，只是这次跳转不替他决定看哪个。
//
// **顺序按 `order` 而不是数组下标**：数组可能是乱序读回来的，按下标取会跳到
// 一个「碰巧排在前面」的块上。
//
// **找不到就明说**：一个点了没反应的节点，用户会以为界面卡了，然后反复点。
// 计划里带 `reason`，让上层能给出一句「这个节点还没有被引用」。
//
// **这一层不碰 DOM**：滚动与高亮时长归调用方。在这里 `scrollIntoView` 的话，
// 容器与偏移量都由这一层猜——而真正知道布局的是上层；两边各滚一次会把页面弹两下。

export type BlockRef = {
  blockId: string;
  /** 文书顺序 */
  order: number;
  /** 这一块引用了哪些图谱节点 */
  sourceNodeIds: string[];
};

export type JumpPlan = {
  found: boolean;
  scrollToBlockId: string | null;
  highlightBlockId: string | null;
  reason: "no_reference" | null;
};

/** 节点 → 文书里**第一处**引用它的 Block（按 order）。找不到回 null。 */
export function firstReferencingBlock(
  blocks: BlockRef[],
  nodeId: string,
): BlockRef | null {
  const referencing = blocks
    .filter((b) => b.sourceNodeIds.includes(nodeId))
    .sort((a, b) => a.order - b.order);
  return referencing[0] ?? null;
}

/** Block → 它引用的来源节点（未知 Block 回空数组，不抛）。 */
export function nodesReferencedByBlock(
  blocks: BlockRef[],
  blockId: string,
): string[] {
  const block = blocks.find((b) => b.blockId === blockId);
  return block ? [...block.sourceNodeIds] : [];
}

/** 点节点时的跳转计划。**纯数据**：谁去滚、高亮多久，由调用方决定。 */
export function planNodeToBlockJump(blocks: BlockRef[], nodeId: string): JumpPlan {
  const target = firstReferencingBlock(blocks, nodeId);
  if (target === null) {
    return {
      found: false,
      scrollToBlockId: null,
      highlightBlockId: null,
      reason: "no_reference",
    };
  }
  return {
    found: true,
    scrollToBlockId: target.blockId,
    highlightBlockId: target.blockId,
    reason: null,
  };
}
