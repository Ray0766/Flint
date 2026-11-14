// 块渲染器（服务端）：按冻结件 BlockContent 判别联合的**全部 8 支**逐一分派，
// 全部复用 components/honesty 既有形态。数据只读、前端零计算；
// 受保护块经 isProtected 判定后整块不渲染控件。
//
// 版式：每个 block = 「出处槽 + 正文」并置。所有状态印记（复核/争议/保护/缺口/阻断）
// 只出现在左侧 EvidenceGutter 里，正文块内不再挂任何徽记，正文保持干净。
import type { Block, InlineSpan, TableCell } from "@/lib/types"
import { DisputedMark } from "@/components/honesty/disputed-mark"
import { CitationMark } from "@/components/honesty/citation-mark"
import { ChannelValue } from "@/components/honesty/channel-value"
import { ChartPlaceholder } from "@/components/honesty/chart-placeholder"
import { GapNotice } from "@/components/honesty/gap-notice"
import { ProtectedBlock } from "@/components/honesty/protected-block"
import { EvidenceGutter } from "@/components/honesty/evidence-gutter"

// 段内 span 分派：text / claim(争议) / cite(可点) / profile(档案出处通道)
function InlineSpans({ spans }: { spans: InlineSpan[] }) {
  return (
    <>
      {spans.map((s, i) => {
        switch (s.kind) {
          case "text":
            return <span key={i}>{s.text}</span>
          case "claim":
            return (
              <DisputedMark key={i} disputed_mark={s.disputed_mark}>
                {s.text}
              </DisputedMark>
            )
          case "cite":
            return <CitationMark key={i} citation_id={s.citation_id} />
          case "profile":
            // profile 是三条出处通道之一（值来自用户档案），不是确定度标记。
            // 走 ChannelValue channel="profile"，绝不套 SpeculativeTag。
            return <ChannelValue key={i} channel="profile" field_path={s.field_path} />
        }
      })}
    </>
  )
}

// 表格 cell 三通道分渲：text / fact / price（quantity 原样，不计算）
// leading=true 表示该 cell 是行首列——行名是**人读的内容**，应是该行主体，
// 故字号高于其后的引用标识符（修「ID 比内容还响」的主次颠倒）。
function Cell({ cell, leading }: { cell: TableCell; leading?: boolean }) {
  switch (cell.kind) {
    case "text":
      return (
        <span
          className={
            leading
              ? "text-[15px] font-medium leading-[1.5] text-foreground"
              : "text-[13px] leading-[1.6] text-foreground"
          }
        >
          {cell.text}
        </span>
      )
    case "fact":
      return <ChannelValue channel="fact" fact_id={cell.fact_id} display={cell.fact_id} />
    case "price":
      return (
        <ChannelValue
          channel="price"
          price_entry_id={cell.price_entry_id}
          quantity={cell.quantity}
          display={cell.price_entry_id}
        />
      )
  }
}

// 「出处槽 + 正文」并置外壳：section 承载锚点 id；槽在左（桌面竖轨/移动内联），正文在右。
function GutterBlock({ block, children }: { block: Block; children: React.ReactNode }) {
  return (
    <section
      id={block.block_id}
      className="mb-6 flex scroll-mt-8 flex-col gap-2 md:flex-row md:gap-3"
    >
      <EvidenceGutter block={block} />
      <div className="min-w-0 flex-1">{children}</div>
    </section>
  )
}

export function BlockRenderer({ block }: { block: Block }) {
  const content = block.content

  // —— declaration：locked 保护块，钉顶，无控件（保护态由左槽 locked 印记承载） ——
  if (content.kind === "declaration") {
    return (
      <GutterBlock block={block}>
        <ProtectedBlock block={block}>
          <p className="font-display text-[20px] leading-[1.3] text-foreground text-balance">
            {content.text}
          </p>
        </ProtectedBlock>
      </GutterBlock>
    )
  }

  // —— paragraph：advisory 可折叠、不挡导出；含争议 claim 与可点 cite（复核/争议印记在左槽） ——
  if (content.kind === "paragraph") {
    const advisory = block.review_severity === "advisory"
    const body = (
      <p className="leading-[1.8] text-foreground">
        <InlineSpans spans={content.spans} />
      </p>
    )
    return (
      <GutterBlock block={block}>
        <div className="rounded-card border border-rule bg-card p-5">
          {advisory ? (
            <details open>
              <summary className="mb-2 inline-block cursor-pointer rounded-[4px] font-mono text-[11px] text-ink-3 focus:outline-none focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2 focus-visible:ring-offset-card">
                可折叠（不挡导出）
              </summary>
              {body}
            </details>
          ) : (
            body
          )}
        </div>
      </GutterBlock>
    )
  }

  // —— table：blocking → 块级 spark 描边强调 + 挡导出（阻断印记在左槽）；cell 三通道分渲 ——
  if (content.kind === "table") {
    const blocking = block.review_severity === "blocking"
    return (
      <GutterBlock block={block}>
        <div
          className={`rounded-card border p-5 ${blocking ? "border-spark bg-spark-wash/40" : "border-rule bg-card"}`}
        >
          {/* 窄屏堆叠、宽屏成表——**同一份 DOM**，靠 display 切换，不复制内容。
              <768px：thead 移出视觉流（仍供读屏），每个 tr 变一张卡，每个 td 前置自己的列名；
              ≥768px：恢复标准表格。NEVER 靠横向滚动硬挤列。 */}
          <table className="block w-full border-collapse text-left md:table">
            <thead className="sr-only md:not-sr-only md:table-header-group">
              <tr className="md:border-b md:border-rule">
                {content.header.map((h, i) => (
                  <th key={i} className="px-3 py-2 font-mono text-[11px] font-normal text-ink-3">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="block md:table-row-group">
              {content.rows.map((row, ri) => (
                <tr
                  key={ri}
                  className="mb-3 block rounded-[4px] border border-rule p-3 last:mb-0 md:mb-0 md:table-row md:rounded-none md:border-0 md:border-b md:border-rule md:p-0 md:align-top md:last:border-0"
                >
                  {row.map((cell, ci) => (
                    <td
                      key={ci}
                      className={`flex min-w-0 flex-col gap-1 border-b border-rule/60 py-2 last:border-0 md:table-cell md:border-0 md:px-3 md:py-4 ${
                        // 行首列（人读的行名）在宽屏占固定份额，避免被长标识符挤到断词
                        ci === 0 ? "md:w-[26%] md:min-w-[8em]" : ""
                      }`}
                    >
                      {/* 窄屏下每格自带列名，脱离表头也读得懂；宽屏隐藏（表头已在） */}
                      <span className="font-mono text-[10px] text-ink-3 md:hidden">
                        {content.header[ci]}
                      </span>
                      <Cell cell={cell} leading={ci === 0} />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </GutterBlock>
    )
  }

  // —— chart：只渲染占位（chart_id + derived_from 出处），零数据点、不引图表库 ——
  // 无任何附加状态 → 左槽为空，空槽轨线仍在（桌面），移动端不占位。
  if (content.kind === "chart") {
    return (
      <GutterBlock block={block}>
        <ChartPlaceholder chart_id={content.chart_id} derived_from="后端 derived_from（接口未建）" />
      </GutterBlock>
    )
  }

  // —— gap_notice：物理切口；author=="user" 为保护块只读，不以生成文字填满（缺口/保护印记在左槽） ——
  if (content.kind === "gap_notice") {
    return (
      <GutterBlock block={block}>
        <ProtectedBlock block={block}>
          <GapNotice hints_ref={content.hints_ref} />
        </ProtectedBlock>
      </GutterBlock>
    )
  }

  // —— heading：章节标题，level 由后端定，前端不重排层级 ——
  if (content.kind === "heading") {
    const size =
      content.level <= 1 ? "text-[31px]" : content.level === 2 ? "text-[25px]" : "text-[20px]"
    return (
      <GutterBlock block={block}>
        <h2 className={`font-display ${size} font-medium leading-[1.3] text-foreground text-balance`}>
          {content.text}
        </h2>
      </GutterBlock>
    )
  }

  // —— quality_card：只有 card_ref，解引用端点未建 → 如实显引用位，不渲染任何指标数字 ——
  if (content.kind === "quality_card") {
    return (
      <GutterBlock block={block}>
        <div className="rounded-card border border-dashed border-rail bg-raised p-5">
          <p className="font-mono text-[11px] text-ink-3">quality_card · card_ref {content.card_ref}</p>
          <p className="mt-2 max-w-[30em] text-[13px] leading-relaxed text-ink-2">
            质量卡引用位。解引用端点（GET /quality-cards/&#123;ref&#125;）尚未提供，故此处只显引用本身，
            NEVER 前端代算覆盖率/对齐率。
          </p>
        </div>
      </GutterBlock>
    )
  }

  // —— citation_list：引用清单，逐条列 citation_id（解引用未建 → 只显 id，不编标题） ——
  if (content.kind === "citation_list") {
    return (
      <GutterBlock block={block}>
        <div className="rounded-card border border-rule bg-card p-5">
          <p className="mb-3 font-mono text-[11px] text-ink-3">
            citation_list · {content.citation_ids.length} 条
          </p>
          {content.citation_ids.length === 0 ? (
            <p className="font-mono text-[12px] text-ink-3">citation_ids 为空数组（本块无引用）。</p>
          ) : (
            <ol className="space-y-1.5">
              {content.citation_ids.map((cid) => (
                <li key={cid} className="font-mono text-[12px] text-ink-2">
                  {cid}
                </li>
              ))}
            </ol>
          )}
        </div>
      </GutterBlock>
    )
  }

  // 判别联合已穷尽 8 支；新增支到达时 TS 会在此报错，而不是静默漏渲。
  return assertNever(content)
}

function assertNever(x: never): null {
  // 运行期兜底：真收到未知 kind 时如实留痕，NEVER 静默吞掉一个块。
  console.error("BlockRenderer: 未知 BlockContent.kind", x)
  return null
}
