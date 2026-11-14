// GRAPH-15：工作台空态（F19，从广场拖入引导）。
//
// 空台**不是错误态**：一张还没放东西的画布是每个新用户的起点。所以这里给的是
// **一条出路**（去广场挑一个热点拖进来），而不是一句「暂无数据」——后者把用户留在原地。
//
// 只说「去广场」也不够：他到了广场还是不知道下一步该做什么。所以引导里带着**动作**
// （把卡片拖进工作台），那正是这张空画布唯一在等的事。
//
// 路由常量复用 FAV-06 的 `PLAZA_ROUTE`，本文件 NEVER 再写一遍 `/plaza`：
// 两处各写一个字符串，改路由时必然漏掉一个。

import type { JSX } from "react";

import { t } from "../../lib/i18n/t";
import { PLAZA_ROUTE } from "../library-empty/LibraryEmpty";

export function WorkbenchEmpty(): JSX.Element {
  return (
    <div data-testid="workbench-empty">
      <p data-testid="workbench-empty-text">{t("workbench.empty")}</p>
      <p data-testid="workbench-empty-hint">{t("workbench.empty.hint")}</p>
      <a data-testid="workbench-empty-cta" href={PLAZA_ROUTE}>
        {t("workbench.empty.cta")}
      </a>
    </div>
  );
}
