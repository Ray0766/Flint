// 状态：ClaimSpan.disputed_mark === true → 波浪下划 + 争议签（标记而不删除原文）
import type { ReactNode } from "react"
import { GitBranch } from "lucide-react"

// 争议标：ClaimSpan.disputed_mark 为真时，对原文加波浪标记并附争议签——
// 是标记不是删除。disputed_mark 为假时原样透传，不加任何装饰。
export function DisputedMark({
  disputed_mark,
  children,
}: {
  disputed_mark: boolean
  children: ReactNode
}) {
  if (!disputed_mark) return <>{children}</>
  return (
    <span className="text-foreground">
      <span className="underline decoration-ink-2 decoration-wavy underline-offset-4">{children}</span>
      <span className="ml-2 inline-flex items-center gap-1 rounded-[4px] border border-rail px-1.5 py-0.5 align-middle font-mono text-[10px] text-ink-2">
        <GitBranch className="h-3 w-3" strokeWidth={1.5} aria-hidden />
        争议
      </span>
    </span>
  )
}
