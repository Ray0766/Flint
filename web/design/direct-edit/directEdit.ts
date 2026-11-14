// DESIGN-10：直接编辑（G14）。
//
// ## 落点顺序：工具类 → inline style，没有第三条路
//
// 同一处改动可以落在三个地方，而它们的**影响半径**天差地别：工具类只影响这一个元素、
// inline style 也只影响这一个、全局 CSS 影响**所有长得像的**元素。
// 用户点着一张卡片说「这里紧一点」，改的却是全站所有卡片——那是他绝不会预期的。
//
// 所以全局 CSS 这条路**根本不存在**（不是「排在最后」）：本模块没有那个入参，
// 也没有任何写 `<style>` 或 `insertRule` 的分支。留一个「最后才用」的口子，
// 早晚会有人在某个说不清的场景里用上它。
//
// 顺序是**硬的**：两者都给时优先工具类，不由调用方临场决定——
// 让调用方决定就等于没有顺序。
//
// ## data-loc 是编辑器的锚，不是产物的一部分
//
// 导出时剥干净：留在产物里等于把开发期的脚手架交付给客户，而且下一次导入时
// 这些锚会与新的编辑器状态对不上号。剥的时候连同多余空格一起收拾——
// `<h1 data-loc="x" class=` 剥完不该变成 `<h1  class=`。

export type LandingSlot = "utility-class" | "inline-style";

/** 落点顺序（硬序）。全局 CSS 不在其中，且本模块无写入它的路径。 */
export const LANDING_ORDER: readonly LandingSlot[] = ["utility-class", "inline-style"];

export type ByteSpan = { start: number; end: number };

export type DirectEdit = {
  loc: string;
  utilityClass: string | null;
  style: Record<string, string> | null;
};

/** 找 data-loc="x" 所在的那个标签，返回它的字节区间。 */
export function findByLoc(html: string, loc: string): ByteSpan | null {
  const anchor = html.indexOf(`data-loc="${loc}"`);
  if (anchor === -1) return null;                   // 找不到就是找不到，NEVER 退而求其次
  const start = html.lastIndexOf("<", anchor);
  const end = html.indexOf(">", anchor);
  if (start === -1 || end === -1) return null;
  return { start, end: end + 1 };
}

function upsertClass(tag: string, utilityClass: string): string {
  const match = /class="([^"]*)"/.exec(tag);
  if (match === null) return tag.replace(/>$/, ` class="${utilityClass}">`);
  return tag.replace(match[0], `class="${match[1]} ${utilityClass}"`);
}

function upsertStyle(tag: string, style: Record<string, string>): string {
  const text = Object.entries(style)
    .map(([k, v]) => `${k}: ${v}`)
    .join("; ");
  const match = /style="([^"]*)"/.exec(tag);
  if (match === null) return tag.replace(/>$/, ` style="${text}">`);
  return tag.replace(match[0], `style="${match[1]}; ${text}"`);
}

export function applyEdit(html: string, edit: DirectEdit): string {
  const span = findByLoc(html, edit.loc);
  if (span === null) throw new Error(`no element at data-loc=${edit.loc}`);
  // undefined 与 null 都算「没给」：只认 null 的话，传一个根本不存在的落点
  // （比如 globalCss）时两个字段都是 undefined，这道检查就静默放行了。
  const utilityClass = edit.utilityClass ?? null;
  const style = edit.style ?? null;
  if (utilityClass === null && style === null) {
    // 一次什么都不改的编辑是调用方算错了；静默返回原样会让那个 bug 一直藏着
    throw new Error(`edit at ${edit.loc} carries neither a utility class nor a style`);
  }

  const tag = html.slice(span.start, span.end);
  const next =
    utilityClass !== null
      ? upsertClass(tag, utilityClass)               // 硬序：工具类优先
      : upsertStyle(tag, style as Record<string, string>);
  return html.slice(0, span.start) + next + html.slice(span.end);
}

const LOC_ATTR = /\s*data-loc=(?:"[^"]*"|'[^']*'|[^\s>]+)/g;

/** 剥掉所有 data-loc（含单引号与无引号写法），不动其它属性。 */
export function stripDataLoc(html: string): string {
  return html.replace(LOC_ATTR, "");
}

/** 导出：产物里零 data-loc。 */
export function exportHtml(html: string): string {
  return stripDataLoc(html);
}
