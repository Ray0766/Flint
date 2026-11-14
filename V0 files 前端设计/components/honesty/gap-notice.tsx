// 状态：GapNoticeContent.hints_ref → 物理切口占位（缺口如实呈现，不以占位数据填充）
import { Scissors } from "lucide-react"
import type { GapNoticeContent } from "@/lib/types"

// 缺口占位：证据链中断处如实留出物理切口。只接 types.ts 的 hints_ref，
// 不发明任何数值或图形填充——缺口本身就是诚实信号。
export function GapNotice({ hints_ref }: Pick<GapNoticeContent, "hints_ref">) {
  return (
    <div className="gap-cut flex min-h-40 flex-col items-center justify-center gap-2 rounded-[4px] px-4 py-6">
      <Scissors className="h-4 w-4 text-ink-3" strokeWidth={1.5} aria-hidden />
      <p className="font-mono text-[12px] text-ink-3">hints_ref · {hints_ref}</p>
      <p className="max-w-[22em] text-center text-[13px] leading-relaxed text-ink-2">
        此处证据链中断，缺口如实呈现，未以占位数据填充。
      </p>
    </div>
  )
}
