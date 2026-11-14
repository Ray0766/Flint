// FIX-17：source id → **屏上看得见的来源名**。
//
// ## 治的病
//
// `SourceColumns` 的全部理由写在它自己的文件头：「读者失去了『谁说的』这个唯一能
// 判断可信度的东西」。而改前它把来源只放进 `data-source-id`——
// **DOM 里有、屏上一个字都没有**。
//
// 两条说法并排，读者判不出哪句是 GitHub 说的、哪句是微博说的。
// `PRINCIPLES#B4` 说「把话还给说话的人」，而话还回去了、人没写上。
//
// 地区那一列不够顶这件事：列标题是地区，只有两个源恰好分属两个区时才顺带区分了它们。
// 库里的实况是 `global = 103 · CN = 89 · NULL = 1`——绝大多数簇的源要么同区要么无区，
// **同一列里两条陈述，谁说的完全看不出来**。
//
// ## 为什么是一张明写的表，不是把前缀与 id 拼起来取词条
//
// 拼出来的 key **grep 不到**：`tools/i18n_key_defined.mjs` 会把它报成未定义，
// 而那份报告是对的——没有人能从源码里看出这个前缀底下到底要有哪几个 key。
// 第 7 批的 `JobDeniedNotice` 正是栽在这一处（模板字面量拼 key）。
//
// 这段说明里也**不写出那个拼法的样子**：扫描器读到的是字符，它分不出
// 「示范」与「在用」——本仓已在这一形状上栽过十四次，每次的修法都是
// 给那句话换个说法，而不是把尺子放宽。
//
// ## 认不出来的 id 原样显示
//
// **NEVER 编一个名字**，也 NEVER 显示成「未知来源」：
// 前者假装我们认识它，后者把「我们没给这个源起过名」说成「这条陈述来路不明」。
// 原样显示那个 id，读者至少知道是**同一个**源在说话——而那正是这个组件要的东西。

import { t } from "../../lib/i18n/t";

/**
 * 四个源的可见名。key **逐个写死**，与 `flint/sources/*.py` 的 `source_id` 对齐
 * （`gtrends` · `weibo` · `ghtrend` · `arxiv`）。
 *
 * 新增一个源时这里要跟着加一行——不加的话它会原样显示 id，
 * 而判据 `test_source_columns_attribution.py` 会当场报出来。
 */
const NAME_KEY: Record<string, string> = {
  gtrends: "source.name.gtrends",
  weibo: "source.name.weibo",
  ghtrend: "source.name.ghtrend",
  arxiv: "source.name.arxiv",
};

/** 屏上写谁说的。认不出来的 id 原样返回。 */
export function sourceName(sourceId: string): string {
  const key = NAME_KEY[sourceId];
  return key === undefined ? sourceId : t(key);
}
