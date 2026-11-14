import type { JSX } from "react";
import type {
  Block,
  BlockContent,
  InlineSpan,
  TableCell,
} from "../../lib/types";
import { isProtected } from "../../lib/types";
import { t } from "../../lib/i18n/t";
import { DerefValue } from "../DerefValue";

// L0 只读块视图：8 类 BlockType 各一只读组件，判别联合穷尽（无一落空）。
// 全组件只读——NEVER 渲染 input/textarea/button 等编辑控件；保护块额外标注。
// chart 只按 chart_id 引用 ChartSpec，前端零计算（D3 铁律）。

function InlineSpanView({ span }: { span: InlineSpan }): JSX.Element {
  switch (span.kind) {
    case "text":
      return <span>{span.text}</span>;
    case "claim":
      return (
        <span data-claim-id={span.claim_id} data-disputed={span.disputed_mark}>
          {span.disputed_mark ? (
            // 争议记号用**几何印记**（_ds 的斜纹方），NEVER 用 ⚠ 这类 emoji：
            // 各平台字形不同、颜色不受 token 控制、读屏会把它读成「警告标志」
            // 而不是这套系统里的「争议」语义（G30 / DESIGN-23）。
            <span
              data-testid="disputed-mark"
              className="mark mark--disputed"
              role="img"
              aria-label={t("block.claim.disputed")}
            />
          ) : null}
          {span.text}
        </span>
      );
    case "cite":
      // FB-09：屏上给文献标题 + 定位符，不再把 citation_id 甩给读者。
      // data-* 留着：那是取证与调试要用的，属开发面，不进产品面（acceptance③）。
      return (
        <sup data-citation-id={span.citation_id}>
          <DerefValue kind="citation" id={span.citation_id} />
        </sup>
      );
    case "profile":
      return <span data-profile-path={span.field_path}>{span.field_path}</span>;
    default:
      return assertNever(span);
  }
}

function TableCellView({ cell }: { cell: TableCell }): JSX.Element {
  switch (cell.kind) {
    case "text":
      return <td>{cell.text}</td>;
    case "fact":
      return (
        <td data-fact-id={cell.fact_id}>
          <DerefValue kind="fact" id={cell.fact_id} />
        </td>
      );
    case "price":
      // 零计算：金额由后端算好给（FB-05），前端只显示，NEVER 自己乘。
      return (
        <td data-price-entry-id={cell.price_entry_id}>
          <DerefValue kind="price" id={cell.price_entry_id} quantity={cell.quantity} />
        </td>
      );
    default:
      return assertNever(cell);
  }
}

function ContentView({ content }: { content: BlockContent }): JSX.Element {
  switch (content.kind) {
    case "heading": {
      const Tag = `h${Math.min(Math.max(content.level, 1), 6)}` as
        keyof JSX.IntrinsicElements;
      return <Tag>{content.text}</Tag>;
    }
    case "paragraph":
      return (
        <p>
          {content.spans.map((span, i) => (
            <InlineSpanView key={i} span={span} />
          ))}
        </p>
      );
    case "table":
      return (
        <table>
          <thead>
            <tr>
              {content.header.map((h, i) => (
                <th key={i}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {content.rows.map((row, ri) => (
              <tr key={ri}>
                {row.map((cell, ci) => (
                  <TableCellView key={ci} cell={cell} />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      );
    case "chart":
      // 前端零计算：只引用 chart_id，数据由后端 ChartSpec.derived_from 反查产出。
      return (
        <figure data-chart-id={content.chart_id} data-render="deferred-to-backend">
          <figcaption>
            <DerefValue kind="chart" id={content.chart_id} />
          </figcaption>
        </figure>
      );
    case "declaration":
      return <aside data-declaration="true">{content.text}</aside>;
    case "quality_card":
      return (
        <section data-quality-card-ref={content.card_ref}>
          <DerefValue kind="card" id={content.card_ref} />
        </section>
      );
    case "citation_list":
      return (
        <ol data-citation-list="true">
          {content.citation_ids.map((cid) => (
            <li key={cid} data-citation-id={cid}>
              {/* FB-09：这一处也在显示 citation_id——截图里那两行 `cit-demo-…`
                  就是它。acceptance① 说的「显示 citation_id 的地方」包含它。 */}
              <DerefValue kind="citation" id={cid} />
            </li>
          ))}
        </ol>
      );
    case "gap_notice":
      return (
        <div data-gap-notice-ref={content.hints_ref}>
          <DerefValue kind="hints" id={content.hints_ref} />
        </div>
      );
    default:
      return assertNever(content);
  }
}

export function BlockView({ block }: { block: Block }): JSX.Element {
  return (
    <div
      data-block-id={block.block_id}
      data-block-type={block.type}
      data-readonly="true"
      data-protected={isProtected(block)}
      data-needs-review={block.needs_review}
    >
      <ContentView content={block.content} />
    </div>
  );
}

// 判别联合穷尽守卫：新增 BlockType 未处理 → 编译期 never 报错（无一落空的静态保证）。
function assertNever(x: never): never {
  throw new Error(`unhandled block content variant: ${JSON.stringify(x)}`);
}
