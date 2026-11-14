// 签名元素 · 出处槽（evidence gutter）
// 正文左侧一条固定宽度竖轨，所有「这段站在什么之上」的印记只出现在槽里，正文保持干净。
// 槽为空 = 这段真的没有附加状态；空槽的轨线仍然渲染，不折叠、不塌陷（空槽本身是信息）。
//
// 唯一派生真相：deriveGutterMarks(block)。缩略带（gutter-minimap）复用同一函数，
// 两者绝不各算各的。印记类型六种：empty / review / disputed / speculative / locked / gap。
import type { Block } from "@/lib/types"
import { isProtected } from "@/lib/types"
import { Eye, GitBranch, CircleDashed, Lock, Scissors } from "lucide-react"

// review 带 severity；其余印记无 severity。empty 不进数组（数组为空即空槽）。
export type GutterMarkKind = "review" | "disputed" | "speculative" | "locked" | "gap"
export interface GutterMark {
  kind: GutterMarkKind
  severity?: "advisory" | "blocking" // 仅 review 使用：blocking 迸出唯一 spark，advisory 静默
}

// —— 唯一派生逻辑：只读 types.ts 字段，前端不重算规则 ——
// needs_review→review（severity 决定形态）；claim.disputed_mark→disputed；
// isProtected→locked；content.kind==='gap_notice'→gap；都不成立→空数组（空槽）。
// speculative 是 span 级确定度标记（SpeculativeTag），不由 block 派生，故不在此产生。
export function deriveGutterMarks(block: Block): GutterMark[] {
  const marks: GutterMark[] = []
  if (block.needs_review) {
    marks.push({
      kind: "review",
      severity: block.review_severity === "blocking" ? "blocking" : "advisory",
    })
  }
  if (
    block.content.kind === "paragraph" &&
    block.content.spans.some((s) => s.kind === "claim" && s.disputed_mark)
  ) {
    marks.push({ kind: "disputed" })
  }
  if (isProtected(block)) marks.push({ kind: "locked" })
  if (block.content.kind === "gap_notice") marks.push({ kind: "gap" })
  return marks
}

// —— 单枚印记渲染：图形/字形区分类别，尺寸恒定，不编码程度 ——
function Mark({ mark }: { mark: GutterMark }) {
  if (mark.kind === "review") {
    if (mark.severity === "blocking") {
      // blocking：全站唯一 spark 出场点之一（导出 409 闸）
      return (
        <span className="inline-flex items-center gap-1 font-mono text-[11px] leading-none text-spark">
          <span className="spark-strike inline-block h-2 w-2 rounded-[1px] bg-spark" aria-hidden />
          阻断
        </span>
      )
    }
    return (
      <span className="inline-flex items-center gap-1 font-mono text-[11px] leading-none text-ink-2">
        <Eye className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />
        复核
      </span>
    )
  }
  if (mark.kind === "disputed") {
    return (
      <span className="inline-flex items-center gap-1 font-mono text-[11px] leading-none text-ink-2">
        <GitBranch className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />
        争议
      </span>
    )
  }
  if (mark.kind === "speculative") {
    return (
      <span className="inline-flex items-center gap-1 font-mono text-[11px] leading-none text-ink-3">
        <CircleDashed className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />
        推测
      </span>
    )
  }
  if (mark.kind === "locked") {
    return (
      <span className="inline-flex items-center gap-1 font-mono text-[11px] leading-none text-ink-2">
        <Lock className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />
        保护
      </span>
    )
  }
  // gap
  return (
    <span className="inline-flex items-center gap-1 font-mono text-[11px] leading-none text-ink-2">
      <Scissors className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />
      缺口
    </span>
  )
}

// 出处槽：接受 block（自派生）或显式 marks（供 styleguide 展示词汇表）。
// 桌面：固定宽竖轨常驻（空槽轨线仍在）。<768px：收为正文首行前的内联印记，
// 无印记时不产生任何占位文字（不塌成空白行）。
export function EvidenceGutter(props: { block: Block } | { marks: GutterMark[] }) {
  const marks = "block" in props ? deriveGutterMarks(props.block) : props.marks

  return (
    <>
      {/* 桌面：左侧竖轨，恒宽；空槽轨线仍渲染 */}
      <div className="hidden shrink-0 md:flex md:w-[88px] md:items-stretch md:gap-2 md:pr-3">
        <div className="gutter-rail w-px min-h-[1.5rem] self-stretch" aria-hidden />
        <div className="flex flex-col gap-1.5 pt-0.5">
          {marks.length === 0 ? (
            <span className="sr-only">出处槽空态：本段无附加状态</span>
          ) : (
            marks.map((m, i) => <Mark key={`${m.kind}-${i}`} mark={m} />)
          )}
        </div>
      </div>

      {/* 移动：无印记则完全不渲染（不占位）；有印记则内联印记置于正文首行前 */}
      {marks.length > 0 ? (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 md:hidden">
          {marks.map((m, i) => (
            <Mark key={`m-${m.kind}-${i}`} mark={m} />
          ))}
        </div>
      ) : null}
    </>
  )
}
