// 状态：Block.needs_review + Block.review_severity + Block.review_reason → 提示/阻断徽记（blocking 用全站唯一 spark）
import { Eye } from "lucide-react"

// 复核徽记：severity=="blocking" 时迸出唯一火星色 spark（并意味导出 409 闸），
// 否则 advisory 静默。字段直取 types.ts 的 review_severity / review_reason。
export function ReviewBadge({
  review_severity,
  review_reason,
}: {
  review_severity: string | null
  review_reason?: string | null
}) {
  const blocking = review_severity === "blocking"
  if (blocking) {
    return (
      <span className="inline-flex items-center gap-2 rounded-[4px] border border-spark px-3 py-1.5 font-mono text-[11px] text-spark">
        <span className="spark-strike inline-block h-2.5 w-2.5 rounded-[1px] bg-spark" aria-hidden />
        {review_reason ?? "blocking · 阻断"}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-ink-2">
      <Eye className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />
      {review_reason ?? "advisory · 提示"}
    </span>
  )
}
