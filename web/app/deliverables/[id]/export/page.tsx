"use client";

import { use, useState, type JSX } from "react";

import { LoadingSkeleton } from "../../../../components/shell/LoadingSkeleton";

import { API_BASE } from "../../../../lib/apiBase";
import { Screen } from "../../../../components/shell/Screen";
import { requestExport, type ExportFormat, type ExportOutcome } from "./exportClient";
import { t } from "../../../../lib/i18n/t";

// UI-02 主链路第四屏：导出（含被闸门阻断的 409 态）。
//
// 风格来源：`Claude design Flint 前端设计/Flint 应用 · 20 屏/Flint 批次三 · 交付物.dc.html`
// 的 P13 导出面板一节。蓝本 README 的导出门禁原话：
// 「409 EXPORT_BLOCKED → detail.blocking_block_ids 高亮待处理块并挡导出；
//  pdf/pack 503 →『该格式暂不可用』，不转圈不伪装下载」。
//
// ## 阻断时说清**原因**与**被阻断的块**（acceptance③）
//
// 只弹一句「导出失败」，用户既不知道为什么，也不知道去哪儿改。
// 这一屏把 `blocking_block_ids` 逐条列出来——那是他要去处理的清单，
// 每条都带一个跳回报告的锚链接。
//
// ## 色彩纪律
//
// `--rust`（`--alert-blocking`）全站仅三处，409 EXPORT_BLOCKED 是其中之一
// （蓝本 Design Tokens 一节原话）。503 **不用** rust：它不是坏消息，是「等一等」。

const FORMATS: readonly ExportFormat[] = ["markdown", "html", "pdf", "docx", "pack"];

export default function ExportPage({
  params,
}: {
  params: Promise<{ id: string }>;
}): JSX.Element {
  const { id } = use(params);
  const [outcome, setOutcome] = useState<ExportOutcome | null>(null);
  const [pending, setPending] = useState<ExportFormat | null>(null);

  async function tryExport(fmt: ExportFormat): Promise<void> {
    setPending(fmt);
    setOutcome(null);
    try {
      setOutcome(await requestExport(id, fmt, { baseUrl: API_BASE }));
    } finally {
      setPending(null);
    }
  }

  return (
    <Screen title={t("export.screen.title")} meta={t("export.screen.meta")}>
      <ul className="data-list" data-export-formats>
        {FORMATS.map((fmt) => (
          <li className="data-row" key={fmt}>
            <span className="data-row__label">{t(`export.format.${fmt}`)}</span>
            <button
              type="button"
              className="workbench-switch__trigger"
              data-export-format={fmt}
              disabled={pending !== null}
              onClick={() => void tryExport(fmt)}
            >
              {t("export.action.render")}
            </button>
          </li>
        ))}
      </ul>

      {/* UIX-01：原先是自造的一行提示。换成通用件——
          `data-export-pending` 这个既有断言面**原样保留**在外层，
          改样式 NEVER 顺手改断言面。 */}
      {pending ? (
        <div data-export-pending>
          <LoadingSkeleton rows={1} label={t("export.pending")} />
        </div>
      ) : null}

      {outcome?.kind === "ok" ? (
        <p data-export-ok={outcome.fmt}>{t("export.ok", { fmt: outcome.fmt })}</p>
      ) : null}

      {outcome?.kind === "blocked" ? (
        <section data-export-blocked={outcome.fmt}>
          {/* 原因先说，再说清单——反过来的话，用户看到一串 id 还不知道它们为什么在这儿。 */}
          <p className="job-failed" data-export-blocked-reason>
            {t("export.blocked.reason", { count: outcome.blockingBlockIds.length })}
          </p>
          <ul className="data-list" data-export-blocking-blocks>
            {outcome.blockingBlockIds.map((blockId) => (
              <li className="data-row" key={blockId}>
                <a
                  className="data-row__value"
                  data-blocking-block={blockId}
                  href={`/deliverables/${id}#${blockId}`}
                >
                  {t("export.blocked.go_to_block")}
                </a>
              </li>
            ))}
          </ul>
          {outcome.violations.length > 0 ? (
            <ul className="data-list" data-export-violations>
              {outcome.violations.map((v) => (
                <li className="data-row" key={v}>
                  <span className="data-row__value">{v}</span>
                </li>
              ))}
            </ul>
          ) : null}
          {/* 一条都没列出来时如实说「后端没给清单」，NEVER 显示一个空列表——
              空列表看起来像「没有块被挡住」，而导出确实被挡住了。 */}
          {outcome.blockingBlockIds.length === 0 && outcome.violations.length === 0 ? (
            <p data-export-blocked-empty>{t("export.blocked.no_detail")}</p>
          ) : null}
        </section>
      ) : null}

      {outcome?.kind === "unavailable" ? (
        <p data-export-unavailable={outcome.fmt}>
          {t("export.unavailable", { fmt: outcome.fmt })}
        </p>
      ) : null}

      {outcome?.kind === "failed" ? (
        <p className="job-failed" data-export-failed={outcome.fmt}>
          {t("export.failed", { status: outcome.status })}
        </p>
      ) : null}
    </Screen>
  );
}
