// 状态：Block.needs_review / ClaimSpan.disputed_mark / GapNoticeContent(kind) → 确定度四级呈现（重量随底气递减）
import type { ReactNode } from "react"

// 四级确定度：cited 最有底气 → speculative → disputed → D_insufficient 最轻、最留白。
// 值域来自 types.ts 的真实信号：cited=有 citation、speculative=派生无出处、
// disputed=ClaimSpan.disputed_mark、insufficient=GapNoticeContent(kind='gap_notice')/D_insufficient。
export type CertaintyKind = "cited" | "speculative" | "disputed" | "insufficient"

const LABEL: Record<CertaintyKind, string> = {
  cited: "cited · 已引用",
  speculative: "speculative · 推测",
  disputed: "disputed · 有争议",
  insufficient: "D_insufficient · 数据不足",
}

export function CertaintyLevel({
  kind,
  children,
}: {
  kind: CertaintyKind
  children?: ReactNode
}) {
  return (
    <div className="bg-card p-5">
      <p className="mb-3 font-mono text-[11px] text-ink-3">{LABEL[kind]}</p>
      {kind === "insufficient" ? (
        <div className="gap-cut flex min-h-[3.5rem] items-center justify-center rounded-[4px] px-4 py-6">
          <p className="font-mono text-[12px] text-ink-3">{children ?? "证据不足以支撑判断"}</p>
        </div>
      ) : (
        <div className={`leading-[1.8] ${kind === "speculative" ? "text-ink-2" : "text-foreground"}`}>{children}</div>
      )}
    </div>
  )
}
