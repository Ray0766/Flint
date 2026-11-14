// 扫描器共用的源码剥注释口径（DESIGN-23 抽出，三把扫描器共用）。
//
// 由来：同一个剥注释函数在 no_hardcoded_models / no_external_fonts /
// lint_no_confidence_viz 里各写了一遍，而它踩过**两次**不同的坑：
//
// 1. `//` 前面不判冒号 → `https://fonts…` 被当成行注释起点，整条 URL 被剥掉，
//    扫描器报「0 处」而其实一处没看见（DESIGN-21 实测的**假绿**）。
// 2. 不归一 CRLF → 行尾留着回车符，而 JS 里 `.` 不匹配它、无 `m` 的 `$` 只认串尾，
//    于是整行注释一个字符都剥不掉，CRLF 文件里的注释被当成代码（**假红**，
//    与 GRAPH-11 在 i18n_scan 上实测到的是同一个坑）。
//
// 两次都在同一处逻辑上，所以抽到这里：改一次，三把尺子一起对。

const CRLF = /\r\n?/g;
const BLOCK_COMMENT = /\/\*[\s\S]*?\*\//g;
// 行注释：`//` 前不能是冒号，否则 `https://…` 会被当成注释起点。
const LINE_COMMENT = /(^|[^:])\/\/.*$/;

/**
 * 去掉注释、归一换行，只留代码。用于「源码里不该出现 X」这类扫描。
 *
 * 块注释被换成**等量的换行**而不是删掉：删掉会让行号整体前移，
 * 于是按行比对的扫描器把注释后面那一行的内容算到注释的行号上——
 * 报出来的位置是错的，而看报告的人会去那一行找一段并不在那里的文字。
 * （I18N-09 实测：`t.ts` 的 JSDoc 被删后，第 29 行被报成未 key 化文案。）
 */
export function codeOnly(text) {
  return text
    .replace(CRLF, "\n")
    .replace(BLOCK_COMMENT, (block) => "\n".repeat((block.match(/\n/g) ?? []).length))
    .split("\n")
    .map((line) => line.replace(LINE_COMMENT, "$1"))
    .join("\n");
}
