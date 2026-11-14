// DESIGN-04：设计系统 `_ds` 挂载（G12）。
//
// `_ds` 副本挂在 `web/public/_ds/`（DEC-007 定的落点），样板与生成产物**引用**
// 它的 CSS 变量，NEVER 自己新建 token。
//
// ## 为什么「不新建 token」比「长得像」更要紧
//
// 新建一个 `--my-blue: #2E4A7E` 看起来和藍染 `#2E4A7D` 一模一样，但设计系统改色时
// 它不会跟着变——半年后界面上会有两种「藍染」，而没有人知道第二种是哪来的。
// 引用 `var(--indigo)` 则永远跟着系统走。
//
// ## 判据放在这里，而不是留给眼睛
//
// `findNewTokenDefinitions` 把「新建 token」变成可机器检查的事：任何
// `--foo: ...` 的**定义**（而不是引用）出现在样板/产物里就是命中。
// 定义与引用的区别正是这条规则的全部：`var(--indigo)` 是引用，`--indigo: #xxx` 是定义。

/** `_ds` 副本在 public 下的根路径（浏览器可直接取）。 */
export const DS_ROOT = "/_ds/flint-design-system-8fd95ba3-cf31-49b6-b9d8-c863f3dc2724";

/** 全局样式表，顺序即 manifest 里的 globalCssPaths（顺序会影响层叠，NEVER 打乱）。 */
export const DS_GLOBAL_CSS: readonly string[] = [
  "fonts/fonts.css",
  "tokens/colors.css",
  "tokens/typography.css",
  "tokens/spacing.css",
  "tokens/texture.css",
  "tokens/base.css",
  "styles.css",
];

/** 拼出可直接放进 <link href> 的地址。 */
export function dsCssHrefs(root: string = DS_ROOT): string[] {
  return DS_GLOBAL_CSS.map((path) => `${root}/${path}`);
}

// 定义 = 名字后面跟着冒号（`--gap: 12px`）；引用是 `var(--gap)`，名字后面是 `)` 或 `,`。
// 起初这里还要求前面是 `;{` 或空白，于是行内 style 里 `style="--gap:12px"` 的第一个
// 定义被漏掉了——藏在属性里不代表不存在。
const DEFINITION = /(--[a-z0-9-]+)\s*:/gi;
const REFERENCE = /var\(\s*(--[a-z0-9-]+)/gi;

/** 源码里**定义**的 token 名（不含引用）。空数组 = 没有新建 token。 */
export function findNewTokenDefinitions(source: string): string[] {
  const found: string[] = [];
  for (const match of source.matchAll(DEFINITION)) {
    found.push(match[1]);
  }
  return [...new Set(found)];
}

/** 源码里**引用**的 token 名。 */
export function findTokenReferences(source: string): string[] {
  const found: string[] = [];
  for (const match of source.matchAll(REFERENCE)) {
    found.push(match[1]);
  }
  return [...new Set(found)];
}

// 引用的 token 是否都在已知集合里。
//
// 引用一个**不存在**的 token 不会报错，只会静默回落到无值——界面上是一处
// 没有颜色的文字或塌掉的间距，而排查时看不出是拼错了名字。
//
// （行注释而非 JSDoc：扫描器对跨行块注释的已知假阳性，见 DEC-013 / 卡 I18N-09。）
export function findUnknownTokenReferences(
  source: string,
  known: readonly string[],
): string[] {
  const knownSet = new Set(known);
  return findTokenReferences(source).filter((name) => !knownSet.has(name));
}
