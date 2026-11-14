// FAV-06：图书馆空态（引导去广场）。
//
// 空态**不是错误态**：没有收藏是新用户的正常起点。所以这里给的是一条出路
// （去广场），而不是一句「暂无数据」——后者把用户留在原地。
//
// 文案全 key 化：NEVER 在组件里硬编码中文（i18n_scan 守着）。

import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

/** 广场路由。与卡片广场（C 组）同一常量来源，NEVER 各处各写一个字符串。 */
export const PLAZA_ROUTE = "/plaza";

export function LibraryEmpty(): JSX.Element {
  return (
    <div data-testid="library-empty-state">
      <p data-testid="library-empty-text">{t("library.empty")}</p>
      <a data-testid="library-empty-cta" href={PLAZA_ROUTE}>
        {t("library.empty.cta")}
      </a>
    </div>
  );
}
