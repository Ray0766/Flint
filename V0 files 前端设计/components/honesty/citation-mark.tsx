// 状态：CitationMark.citation_id → 可点角标，浮层展示出处；解引用接口未建则如实写"接口未提供"
"use client"

import { useState } from "react"
import type { CitationMark as CitationMarkModel } from "@/lib/types"

// 出处角标：点击打开浮层。citation_id 的解引用接口尚未建立，
// 浮层内如实写"接口未提供"——不发明出处内容、不静默失败。
export function CitationMark({ citation_id }: Pick<CitationMarkModel, "citation_id">) {
  const [open, setOpen] = useState(false)
  return (
    <span className="relative inline-block align-baseline">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="ml-0.5 rounded-[1px] font-mono text-[11px] text-ink-2 underline decoration-dotted underline-offset-2 transition-colors hover:text-foreground focus:outline-none focus-visible:ring-1 focus-visible:ring-ink-3"
      >
        ⟦{citation_id}⟧
      </button>
      {open ? (
        <span
          role="dialog"
          className="absolute left-0 top-full z-10 mt-1 block w-64 rounded-[4px] border border-rail bg-card p-3 shadow-sm"
        >
          <span className="mb-1 block font-mono text-[11px] text-ink-3">citation_id · {citation_id}</span>
          <span className="block font-mono text-[11px] leading-relaxed text-ink-2">
            解引用接口未提供，无法展示出处详情。
          </span>
        </span>
      ) : null}
    </span>
  )
}
