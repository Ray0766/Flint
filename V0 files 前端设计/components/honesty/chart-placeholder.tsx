// 状态：ChartContent.chart_id (+ derived_from 出处) → 图表占位（前端零计算、不引图表库）
import type { ChartContent } from "@/lib/types"

// 图表占位：只接 chart_id 与出处引用 derived_from，零数据点、不 import 任何图表库。
// 图由后端渲染，前端只声明"这里将有一张图"及其出处，绝不前端计算。
export function ChartPlaceholder({
  chart_id,
  derived_from,
}: Pick<ChartContent, "chart_id"> & { derived_from?: string }) {
  return (
    <div className="flex h-40 flex-col items-center justify-center gap-1 rounded-[4px] border border-dashed border-rail bg-secondary/40">
      <p className="font-mono text-[12px] text-ink-3">chart_id · {chart_id} · 图表区（前端不计算）</p>
      {derived_from ? <p className="font-mono text-[11px] text-ink-3">derived_from · {derived_from}</p> : null}
    </div>
  )
}
