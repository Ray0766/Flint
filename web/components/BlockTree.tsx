import type { JSX } from "react";
import type { Block } from "../lib/types";
import { BlockView } from "./blocks/BlockView";

// L0 只读渲染树：按 section_id 分节、节内按 Block.order 稳定升序。
// 纯只读展示，NEVER 回写、NEVER 计算（Block 树是唯一真相 D3）。

function groupBySection(blocks: Block[]): [string, Block[]][] {
  const order: string[] = [];
  const bySection = new Map<string, Block[]>();
  for (const b of blocks) {
    if (!bySection.has(b.section_id)) {
      bySection.set(b.section_id, []);
      order.push(b.section_id);
    }
    bySection.get(b.section_id)!.push(b);
  }
  return order.map((sid) => [
    sid,
    [...bySection.get(sid)!].sort((a, b) => a.order - b.order),
  ]);
}

export function BlockTree({ blocks }: { blocks: Block[] }): JSX.Element {
  const sections = groupBySection(blocks);
  return (
    <article data-block-tree="true" data-readonly="true">
      {sections.map(([sid, sectionBlocks]) => (
        <section key={sid} data-section-id={sid}>
          {sectionBlocks.map((block) => (
            <BlockView key={block.block_id} block={block} />
          ))}
        </section>
      ))}
    </article>
  );
}
