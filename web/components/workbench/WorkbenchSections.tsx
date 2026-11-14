"use client";

import { useEffect, useState, type JSX } from "react";

import { API_BASE } from "../../lib/apiBase";
import { fetchQuality } from "../../lib/deliverableClient";
import { SECTION_TABLES, type SectionRow } from "../../lib/sectionTables.generated";
import { t } from "../../lib/i18n/t";

/**
 * `WB-05`：右栏那条 sticky 章节导航 + 逐章检查项。
 *
 * 蓝本：`position:sticky; width:138px` 的一列，点章节跳到该章，
 * 每章旁边写占比、字数区间与那句检查问句。
 *
 * ## 章节表**不是在这里写的**
 *
 * 它由 `tools/gen_section_tables.py` 从 `assets/templates/*.yaml`（后端的模板真相）
 * 生成到 `lib/sectionTables.generated.ts`，判据每次跑都用 `--check` 核一遍。
 * 手抄一份的话，两处会在某次改模板之后分叉，而分叉的症状是
 * 「章节导航里有一章，正文里永远没有它」——屏上看不出是抄错了还是没生成。
 *
 * 显示名走 `messages/{zh,en}.json` 的 `wb.section.<模板>.<章节>`：
 * **按模板分键**，因为同一个 `timeline` 在基金申请里叫「时间表」、
 * 在论文开题里叫「时间线」（蓝本逐字）。压成一个键的话，其中一套会显示另一套的名字。
 *
 * ## 「是否满足」**只能从后端来**，而今天它没有出处
 *
 * 工单原话：拿不到判定时显示「还没有判定」而不是显示「通过」。
 * 判定的出处只可能是 `GET /deliverables/{id}/quality`，而那里有**两层**问题：
 *
 * 1. 那一族**没配后端**（实测 503 `FAMILY_NOT_CONFIGURED{family:quality}`）；
 * 2. **就算配上了它也没有章一级的格子**——它报的是整份交付物的质量
 *    （引用覆盖 / 未解析引用 / 缺口引用 / 阻断态四项，见 `QualityReport`）。
 *
 * 所以每一章都是「还没有判定」，且那**不是**临时状态。
 * 单：`docs/blocked/QUALITY-FAMILY-HAS-NO-BACKEND.md`。
 * 前端 NEVER 自己看一眼有没有块就说「通过」：
 * 「这一章有字」与「这一章过了检查」是两件事。
 */

export type WorkbenchSectionsProps = {
  /** 哪一套模板（`WB-06` 的切换把它传下来；地址栏 `?template=` 同样认）。 */
  templateId: string;
  /** 正文里真的有哪些章（`Block.section_id` 去重）——用来说「这一章还没写」。 */
  presentSectionIds: string[];
  /** 当前交付物：拿它去问逐章判定。没有就没得问。 */
  deliverableId?: string | null;
};

type Verdicts = Record<string, boolean>;

export function WorkbenchSections({
  templateId,
  presentSectionIds,
  deliverableId,
}: WorkbenchSectionsProps): JSX.Element | null {
  const rows: SectionRow[] | undefined = SECTION_TABLES[templateId];
  const [verdicts, setVerdicts] = useState<Verdicts | null>(null);

  useEffect(() => {
    if (!deliverableId) {
      setVerdicts(null);
      return;
    }
    let live = true;
    // 走既有客户端（`fetchQuality`）：它把「没配后端 / 取不到」统一收成 `null`，
    // 而 `null` 在这一屏的意思是**还没有判定**——NEVER 当成「通过」。
    void fetchQuality(deliverableId, API_BASE)
      .then((report) => {
        if (!live) return;
        // 那份答复里**没有**章一级的格子（见文件头第 2 条）。
        // 有一天有了，接的地方就是这里：`report.sections` 之类。
        setVerdicts(report === null ? null : {});
      })
      .catch(() => { if (live) setVerdicts(null); });
    return () => { live = false; };
  }, [deliverableId]);

  if (!rows) return null;

  return (
    <nav className="wb-sections" data-wb-sections={templateId} aria-label={t("wb.sections.title")}>
      <h2 className="wb-sections__title">{t("wb.sections.title")}</h2>
      <ol className="wb-sections__list">
        {rows.map((row) => {
          const present = presentSectionIds.includes(row.id);
          const verdict = verdicts?.[row.id];
          return (
            <li
              key={row.id}
              className="wb-sections__item"
              data-wb-section={row.id}
              data-wb-section-present={present ? "true" : "false"}
              data-wb-section-verdict={
                verdict === undefined ? "unknown" : verdict ? "pass" : "fail"
              }
            >
              {/* 跳转落在 `BlockTree` 已有的 `data-section-id` 上——
                  那个属性是它渲染每一节时本来就带的，**不用去改那个封版件**。
                  用按钮而不是 `<a href="#…">`：正文里没有这一章时，
                  一个点不动的链接看起来像坏了；按钮可以**禁用并说出为什么**。 */}
              <button
                type="button"
                className="wb-sections__jump"
                data-wb-section-jump={row.id}
                disabled={!present}
                title={t("wb.sections.jump")}
                onClick={() => {
                  document.querySelector(`[data-section-id="${row.id}"]`)
                    ?.scrollIntoView({ behavior: "smooth", block: "start" });
                }}
              >
                {t(`wb.section.${templateId}.${row.id}`)}
              </button>
              <span className="wb-sections__meta">
                {t("wb.sections.meta", {
                  share: row.share, min: row.minWords, max: row.maxWords,
                })}
              </span>
              {/* 检查问句照模板原文，**一个字不改写**。它在词典里
                  （`wb.check.<模板>.<章节>`，由同一个生成器从 yaml 写入）——
                  放进那份生成的 TS 里的话，CJK 扫描器会当场判红，而它扫得对。 */}
              <span className="wb-sections__check" data-wb-section-check={row.id}>
                {t(`wb.check.${templateId}.${row.id}`)}
              </span>
              {/* 三态各说各的。**「还没有判定」NEVER 显示成「通过」**：
                  前者是「没人查过」，后者是「查过了没问题」。 */}
              <span className="wb-sections__verdict">
                {verdict === undefined
                  ? t("wb.sections.check_unknown")
                  : verdict
                    ? t("wb.sections.check_pass")
                    : t("wb.sections.check_fail")}
              </span>
              {present ? null : (
                <span className="wb-sections__absent">{t("wb.sections.absent")}</span>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
