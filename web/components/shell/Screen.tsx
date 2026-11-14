import type { JSX, ReactNode } from "react";

import { DsStickerTag } from "./DsStickerTag";

/**
 * UI-01 / 屏级容器：标题 + mono 副标 + 正文区。
 *
 * ## 风格来源
 *
 * 蓝本 `Flint 批次一 · 外壳与入口.dc.html` 各功能屏的屏头形状：
 * 页面级标题走 display 字体，右侧一行 mono 副标（`--font-mono` +
 * `tabular-nums`，蓝本原话「一切带出处数值/id/时间戳」走 mono）。
 *
 * ## 副标写什么
 *
 * 写**这一屏是什么**，NEVER 写端点路径或内部 id（FB-10 的 A 类）。
 * 屏名本身是产品语言，端点名不是。
 *
 * ## DS-01：副标改由 `_ds` 的贴纸标签承载
 *
 * 改前：`<p className="screen__meta">{meta}</p>`，一行裸文字，靠 `globals.css` 里
 * 十来行样式扮 mono 副标。
 * 改后：文字外面套一层 `DsStickerTag`（`_ds` 的原件），`.screen__meta` 那一层与它的
 * 文本内容**原样保留**——既有判据（`shell.test.tsx` 断言 `.screen__meta` 的 textContent）
 * 一条都没动。
 *
 * 为什么非改不可：`_ds_bundle.js` 接上之后必须有**一处真正在用它**，否则「接上了」
 * 与「接了但屏上一处都没有」在判据上长得一模一样——那正是本批要治的病。
 * 屏头副标是 `_ds` 的 Type 纪律里贴纸标签的典型位置（mono + 数值/日期/id），
 * 不是为了凑一个用例硬塞的。
 */
export function Screen({
  title,
  meta,
  longform,
  children,
}: {
  title: string;
  meta?: string;
  /**
   * 这一屏的正文**是不是长文**（报告正文、计划书正文）。
   *
   * `WIDTH-01`：外壳放宽到 `--width-app-inset` 之后，
   * 长文屏要**自己声明**它需要阅读行长（`--measure-longform`）——
   * 一行 1440px 的中文正文读起来会不断丢行。
   *
   * 由屏自己声明，NEVER 在 CSS 里按屏名一个个列举：
   * 列举的那份清单会漏掉下一个新屏，而漏掉的症状是「这一屏字太长」，
   * 没有人会想到去看一份 CSS 里的屏名清单。
   */
  longform?: boolean;
  children: ReactNode;
}): JSX.Element {
  return (
    <section className={longform ? "screen screen--longform" : "screen"}>
      <header className="screen__header">
        <h1 className="screen__title">{title}</h1>
        {meta ? (
          <p className="screen__meta">
            <DsStickerTag tone="paper">{meta}</DsStickerTag>
          </p>
        ) : null}
      </header>
      <div className="screen__body">{children}</div>
    </section>
  );
}
