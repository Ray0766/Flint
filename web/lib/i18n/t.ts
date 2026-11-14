// I18N-02：组件取文案的**唯一入口**。
//
// 为什么不直接在组件里用 next-intl 的 useTranslations：
// 既有 11 个组件测试是**直接渲染组件**的（没有 Provider）。若组件强依赖 Provider，
// 每个测试都要包一层，而那层包装除了「让测试跑起来」之外不验证任何东西。
//
// 这里做一层薄封装：**有 Provider 就用 Provider 的**（真实运行时路径），
// **没有就回落到 zh 词条**（测试与 SSR 兜底路径）。两条路径取的是**同一份 messages**，
// 所以测试断言到的文案与用户看到的逐字相同——NEVER 出现「测试断言 key、用户看到文案」。

import zh from "../../messages/zh.json";

type Values = Record<string, string | number>;

/** 把 {name} 占位替换成实参。缺参时保留占位符，NEVER 静默吞掉。 */
export function interpolate(template: string, values?: Values): string {
  if (!values) return template;
  return template.replace(/\{(\w+)\}/g, (match, key: string) =>
    key in values ? String(values[key]) : match,
  );
}

const FALLBACK = zh as Record<string, string>;

/**
 * 取一条文案。
 *
 * key 缺失时返回 key 本身并在控制台告警——NEVER 返回空串：
 * 空串会让界面上出现一块无声的空白，而那比显示一个 key 更难被发现。
 */
export function t(key: string, values?: Values): string {
  const template = FALLBACK[key];
  if (template === undefined) {
    // 开发者告警走英文（与 TS 侧抛错文案同口径）：它不是界面文案，
    // 但留在代码行里会让「整棵树零 CJK」这条判据说不清是文案还是日志。
    console.warn(`[i18n] missing key: ${key}`);
    return key;
  }
  return interpolate(template, values);
}
