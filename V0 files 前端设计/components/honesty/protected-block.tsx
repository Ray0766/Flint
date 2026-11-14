// 状态：isProtected(block)=locked ∨ author=='user' ∨ user_modified → 受保护时整块不渲染编辑控件
import type { ReactNode } from "react"
import { Lock } from "lucide-react"
import { isProtected, type Block } from "@/lib/types"

// 保护块：保护条件成立时 controls 分支根本不进入渲染树——是"不渲染"，不是 disabled。
// 保护判定唯一来源为 types.ts 的 isProtected(block)，前端不重算规则。
export function ProtectedBlock({
  block,
  children,
  controls,
}: {
  block: Block
  children: ReactNode
  controls?: ReactNode
}) {
  const protectedNow = isProtected(block)
  return (
    <div className={`rounded-card border bg-card p-5 ${protectedNow ? "border-rail" : "border-rule"}`}>
      {protectedNow ? (
        <p className="mb-3 flex items-center gap-1.5 font-mono text-[11px] text-ink-2">
          <Lock className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />
          保护块 · {block.locked ? "locked" : block.author === "user" ? "author=user" : "user_modified"}
        </p>
      ) : (
        <p className="mb-3 font-mono text-[11px] text-ink-3">普通块 · author={block.author}</p>
      )}

      <div className="leading-[1.8] text-foreground">{children}</div>

      {protectedNow ? (
        <div className="mt-4 border-t border-rule pt-4">
          <p className="font-mono text-[11px] text-ink-3">受保护 · 不提供编辑控件</p>
        </div>
      ) : controls ? (
        <div className="mt-4 flex items-center gap-2 border-t border-rule pt-4">{controls}</div>
      ) : null}
    </div>
  )
}
