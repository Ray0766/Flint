// DESIGN-19：多页面文档（G25，L0 概览 + 章节；375px 无横滚）。
//
// **横向滚动在手机上是看不见的丢失**：用户不知道右边还有内容，他只会觉得这一段
// 写得没头没尾。而横滚最常见的来源不是文字，是某个**写死宽度**的容器
// （表格、代码块、图）。所以约束落在容器样式上（`max-width:100%` + `overflow-x:hidden`），
// 且外壳与每一页都要有——溢出的往往是页，不是外壳。
//
// **没有 L0 就说没有**：NEVER 把第一章顶上来充当概览。顶上来的话，
// 用户点「概览」看到的是「市场」，而他以为那就是全文的开头。
//
// **多个 L0 时取第一个并报出重复**：结构错了要说出来，静默挑一个会让作者
// 一直以为自己那份大纲是对的。

import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

/** 手机基准宽度（卡上 acceptance 的 375px）。此处是**判据**，不是写死的容器宽度。 */
export const MOBILE_WIDTH_PX = 375;

export type DocPage = {
  pageId: string;
  title: string;
  /** 0 = L0 概览；≥1 = 章节 */
  level: number;
  html: string;
};

export type DocOutline = {
  overviewId: string | null;
  sectionIds: string[];
  duplicateOverviewIds: string[];
};

export function buildOutline(pages: DocPage[]): DocOutline {
  const overviews = pages.filter((p) => p.level === 0);
  const [first, ...extra] = overviews;
  return {
    overviewId: first?.pageId ?? null,
    sectionIds: pages.filter((p) => p.level > 0).map((p) => p.pageId),
    duplicateOverviewIds: extra.map((p) => p.pageId),
  };
}

const NO_H_SCROLL = { maxWidth: "100%", overflowX: "hidden" } as const;

export function MultiPageDoc({ pages }: { pages: DocPage[] }): JSX.Element | null {
  if (pages.length === 0) return null;

  const outline = buildOutline(pages);
  const byId = new Map(pages.map((p) => [p.pageId, p]));
  const overview = outline.overviewId ? byId.get(outline.overviewId) : undefined;

  return (
    <div data-testid="multipage-doc" data-page-count={pages.length} style={NO_H_SCROLL}>
      <nav data-testid="doc-outline" aria-label={t("design.doc.outline")}>
        {pages.map((page) => (
          <a
            key={page.pageId}
            data-testid="doc-outline-item"
            data-page-id={page.pageId}
            data-level={page.level}
            href={`#${page.pageId}`}
          >
            {page.title}
          </a>
        ))}
      </nav>
      {overview ? (
        <iframe
          id={overview.pageId}
          data-testid="doc-overview"
          title={overview.title}
          sandbox="allow-scripts allow-forms"
          srcDoc={overview.html}
          style={NO_H_SCROLL}
        />
      ) : null}
      {outline.sectionIds.map((id) => {
        const page = byId.get(id);
        if (page === undefined) return null;
        return (
          <iframe
            key={id}
            id={id}
            data-testid="doc-section"
            data-page-id={id}
            title={page.title}
            sandbox="allow-scripts allow-forms"
            srcDoc={page.html}
            style={NO_H_SCROLL}
          />
        );
      })}
    </div>
  );
}
