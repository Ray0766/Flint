// 报告交互外壳（client）：只承载**真导出**交互与缩略带联动。
// 数据由服务端页面读好后以 props 传入，本组件不读 mock、不计算任何数据值。
//
// 导出一律真打 GET /deliverables/{id}/render?fmt=：
//   200 → 落盘（markdown/html/docx）
//   409 EXPORT_BLOCKED  → 后端门禁（M3-037）拒绝，detail.blocking_block_ids 高亮待处理块
//   503 SERVICE_UNAVAILABLE → pdf 引擎缺失 / pack builder 未接线，可读降级态
// 能不能导出**由后端说了算**：前端 NEVER 预判、NEVER 提前灰掉按钮伪装"没有问题"。
"use client"

import { useState } from "react"
import { FileDown, Package, TriangleAlert, CircleSlash, PlugZap, Loader2 } from "lucide-react"
import type { Block } from "@/lib/types"
import { FlintApiError, FlintNetworkError, renderDeliverable, type RenderFmt } from "@/lib/api"
import { GutterMinimap } from "@/components/primitives/gutter-minimap"

type ExportState =
  | { status: "idle" }
  | { status: "pending"; fmt: RenderFmt }
  | { status: "ok"; fmt: RenderFmt; filename: string }
  | { status: "blocked"; fmt: RenderFmt; error: FlintApiError } // 409 EXPORT_BLOCKED
  | { status: "degraded"; fmt: RenderFmt; error: FlintApiError } // 503 SERVICE_UNAVAILABLE
  | { status: "error"; fmt: RenderFmt; error: unknown } // 其余 4xx/5xx / 连不上

const FMT_EXT: Record<RenderFmt, string> = {
  markdown: "md",
  html: "html",
  pdf: "pdf",
  docx: "docx",
  pack: "zip",
}

export function ReportShell({
  deliverableId,
  blocks,
  renderedBlocks,
}: {
  deliverableId: string
  blocks: Block[]
  renderedBlocks: { id: string; node: React.ReactNode }[]
}) {
  const [exportState, setExportState] = useState<ExportState>({ status: "idle" })

  const doExport = async (fmt: RenderFmt) => {
    setExportState({ status: "pending", fmt })
    try {
      const res = await renderDeliverable(deliverableId, fmt)
      const blob = await res.blob()
      const filename = `${deliverableId}.${FMT_EXT[fmt]}`
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = filename
      a.click()
      URL.revokeObjectURL(url)
      setExportState({ status: "ok", fmt, filename })
    } catch (err) {
      if (err instanceof FlintApiError && err.status === 409) {
        setExportState({ status: "blocked", fmt, error: err })
      } else if (err instanceof FlintApiError && err.status === 503) {
        setExportState({ status: "degraded", fmt, error: err })
      } else {
        setExportState({ status: "error", fmt, error: err })
      }
    }
  }

  const blockingIds = exportState.status === "blocked" ? exportState.error.blockingBlockIds : []
  const busy = exportState.status === "pending"

  const Btn = ({
    fmt,
    icon,
    label,
    primary,
  }: {
    fmt: RenderFmt
    icon: React.ReactNode
    label: string
    primary?: boolean
  }) => (
    <button
      type="button"
      disabled={busy}
      onClick={() => void doExport(fmt)}
      className={`inline-flex items-center gap-1.5 rounded-[4px] border px-3 py-1.5 font-mono text-[12px] transition-opacity disabled:opacity-50 ${
        primary
          ? "border-ink bg-ink text-primary-foreground hover:opacity-90"
          : "border-rule bg-card text-ink-2 hover:border-rail"
      }`}
    >
      {busy && exportState.fmt === fmt ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={1.5} aria-hidden />
      ) : (
        icon
      )}
      {label}
    </button>
  )

  return (
    <div className="flex gap-6">
      {/* 正文栏：max 34em */}
      <div className="min-w-0 flex-1">
        {/* 导出条：每个格式都真打后端 */}
        <div className="mb-6 flex flex-wrap items-center gap-2 border-b border-rule pb-4">
          <Btn
            fmt="markdown"
            primary
            label="导出 markdown"
            icon={<FileDown className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />}
          />
          <Btn
            fmt="docx"
            label="docx"
            icon={<FileDown className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />}
          />
          <Btn
            fmt="pdf"
            label="PDF"
            icon={<FileDown className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />}
          />
          <Btn
            fmt="pack"
            label="打包 vibe_pack"
            icon={<Package className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />}
          />
        </div>

        {/* 200：真落盘 */}
        {exportState.status === "ok" ? (
          <div role="status" className="mb-6 rounded-[4px] border border-rule bg-card px-4 py-3">
            <p className="font-mono text-[12px] text-ink-2">
              200 · {exportState.fmt} 已由后端渲染并下载 · {exportState.filename}
            </p>
          </div>
        ) : null}

        {/* 409：阻塞导出提示（唯一 spark 语义之一） */}
        {exportState.status === "blocked" ? (
          <div role="alert" className="mb-6 rounded-[4px] border border-spark bg-spark-wash px-4 py-3">
            <p className="flex items-center gap-2 font-mono text-[12px] text-spark">
              <TriangleAlert className="h-4 w-4" strokeWidth={1.5} aria-hidden />
              409 · {exportState.error.code} · {exportState.error.message}
            </p>
            <p className="mt-2 font-mono text-[11px] text-ink-2">
              待处理块 · blocking_block_ids ={" "}
              {blockingIds.length > 0
                ? blockingIds.map((id) => (
                    <a
                      key={id}
                      href={`#${id}`}
                      className="mr-1 underline decoration-spark/60 underline-offset-2"
                    >
                      {id}
                    </a>
                  ))
                : "[]（后端未携块清单）"}
            </p>
          </div>
        ) : null}

        {/* 503：可读降级态（非报警红，克制中性） */}
        {exportState.status === "degraded" ? (
          <div
            role="status"
            className="mb-6 rounded-[4px] border border-dashed border-rail bg-secondary/40 px-4 py-3"
          >
            <p className="flex items-center gap-2 font-mono text-[12px] text-ink-2">
              <CircleSlash className="h-4 w-4" strokeWidth={1.5} aria-hidden />
              503 · {exportState.error.code} · {exportState.error.message}
            </p>
            <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
              该格式的渲染依赖暂不可用，导出功能降级。可改用其它格式，或先在线查看本报告——报告内容不受影响。
            </p>
          </div>
        ) : null}

        {/* 其余错误（含连不上后端与 5xx）：如实抬起，不吞 */}
        {exportState.status === "error" ? (
          <div role="alert" className="mb-6 rounded-[4px] border border-spark bg-spark-wash px-4 py-3">
            <p className="flex items-center gap-2 font-mono text-[12px] text-spark">
              {exportState.error instanceof FlintNetworkError ? (
                <PlugZap className="h-4 w-4" strokeWidth={1.5} aria-hidden />
              ) : (
                <TriangleAlert className="h-4 w-4" strokeWidth={1.5} aria-hidden />
              )}
              {exportState.error instanceof FlintApiError
                ? `${exportState.error.status} · ${exportState.error.code}`
                : "导出失败"}
            </p>
            <p className="mt-2 text-[13px] leading-relaxed text-ink-2">
              {exportState.error instanceof Error ? exportState.error.message : String(exportState.error)}
            </p>
          </div>
        ) : null}

        {/* 正文块（服务端渲染）：每块含左侧出处槽（~88px）+ 正文，容器放宽以保正文约 34em 可读宽度。
            blocking 命中时对应块高亮。 */}
        <div className="mx-auto max-w-[42em]">
          {renderedBlocks.map(({ id, node }) => {
            const hit = blockingIds.includes(id)
            return (
              <div
                key={id}
                className={
                  hit
                    ? "rounded-card ring-2 ring-spark ring-offset-4 ring-offset-background transition-shadow"
                    : undefined
                }
              >
                {node}
              </div>
            )
          })}
        </div>
      </div>

      {/* 右侧出处槽缩略带 */}
      <aside className="sticky top-8 hidden h-fit w-16 shrink-0 self-start md:block">
        <GutterMinimap blocks={blocks} />
      </aside>
    </div>
  )
}
