// 状态：无 citation_id 支撑的派生判断 → 虚线下划 + 降权墨（推测，非事实）
import type { ReactNode } from "react"
import { CircleDashed } from "lucide-react"

// 推测：types.ts 没有独立 speculative 字段——它是"有 claim/paragraph 但无 CitationMark 支撑"
// 的派生态。降权呈现：虚线下划 + ink-2，可选尾随一枚推测签。
export function SpeculativeTag({
  children,
  showBadge = false,
}: {
  children: ReactNode
  showBadge?: boolean
}) {
  return (
    <span className="text-ink-2">
      <span className="underline decoration-ink-3 decoration-dashed underline-offset-4">{children}</span>
      {showBadge ? (
        <span className="ml-2 inline-flex items-center gap-1 rounded-[4px] border border-rail px-1.5 py-0.5 align-middle font-mono text-[10px] text-ink-3">
          <CircleDashed className="h-3 w-3" strokeWidth={1.5} aria-hidden />
          推测
        </span>
      ) : null}
    </span>
  )
}
