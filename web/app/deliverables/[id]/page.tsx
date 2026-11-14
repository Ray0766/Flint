import type { JSX } from "react";
import { fetchBlocks, DeliverableNotFound } from "../../../lib/deliverableClient";
import { t } from "../../../lib/i18n/t";
import { BlockTree } from "../../../components/BlockTree";
import { Screen } from "../../../components/shell/Screen";

// L0 只读页面（App Router 服务器组件）：拉 FE-000 结构化 Block 树 → BlockTree 只读渲染。
// 只读，NEVER 回写（Block 树唯一真相 D3）。API 基址经 FLINT_API_BASE 注入。
//
// UI-01 重做的是样式面：套上屏头。**BlockTree 内部一行没动**——它有自己的
// 保护块与记号规则（FB-02 的争议记号、DESIGN 系列的门控），
// 顺手改渲染就等于在样式卡里动判定面。
// 未找到态也套同一个屏头：`data-not-found` 断言属性原样保留。

export default async function DeliverablePage({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<JSX.Element> {
  const { id } = await params;
  const base = process.env.FLINT_API_BASE ?? "";
  try {
    const blocks = await fetchBlocks(id, base);
    return (
      <Screen
        title={t("deliverable.screen.title")}
        meta={t("deliverable.screen.meta")}
        // `WIDTH-01`：**报告正文是长文**——它照旧走 `--measure-longform`
        // （34em 阅读行长）。外壳放宽的是应用容器，不是一行能读多少字。
        longform
      >
        <BlockTree blocks={blocks} />
        {/* UI-02：主链路第三屏 → 第四屏的入口。这个链接是无条件可点的——
            导出屏自己会把 409 阻断态说清楚，把入口藏起来反而让用户不知道
            「为什么导不出」（那正是 acceptance③ 要挡的形状）。 */}
        <p className="data-row" data-export-entry>
          <span className="data-row__label">{t("deliverable.export_entry.label")}</span>
          <a className="data-row__value" data-export-link href={`/deliverables/${id}/export`}>
            {t("deliverable.export_entry.open")}
          </a>
        </p>
        {/* NAV-05：报告的三个同族屏。它们建好之后**一个都点不到**
            （质量卡 UI-09 · vibe_pack UI-10 · 干预页 CHAIN-05），
            而三条都只需要这一屏手上就有的交付物 id。

            与导出那条同一口径：链接**无条件可点**，各屏自己把没数据、
            没接口说清楚。按状态藏入口的话，用户不知道有这个能力，
            而藏起来的理由（"反正也没数据"）恰恰是他最该看到的那句话。

            **受众分叉不在这里**：那一屏按项目走，而交付物 → 项目
            没有可读的对应关系（blocks 回的只有 `{deliverable_id, blocks}`）。
            从这里接就得猜一个项目 id。它从项目总览进。 */}
        <p className="data-row" data-deliverable-siblings>
          <span className="data-row__label">{t("deliverable.more.label")}</span>
          <a
            className="data-row__value"
            data-quality-link
            href={`/deliverables/${id}/quality`}
          >
            {t("deliverable.more.quality")}
          </a>
          <a className="data-row__value" data-pack-link href={`/deliverables/${id}/pack`}>
            {t("deliverable.more.pack")}
          </a>
          <a
            className="data-row__value"
            data-interventions-link
            href={`/deliverables/${id}/interventions`}
          >
            {t("deliverable.more.interventions")}
          </a>
        </p>
      </Screen>
    );
  } catch (err) {
    if (err instanceof DeliverableNotFound) {
      return (
        <Screen title={t("deliverable.screen.title")}>
          <p data-not-found="true">{t("deliverable.not_found", { id })}</p>
        </Screen>
      );
    }
    throw err;
  }
}
