// v0.3 遗留词条表的**去处**（I18N-09 / DEC-013）。
//
// 这里原本是一张独立的 key→中文 表，与 `web/messages/{zh,en}.json` 重复。
// 两张表并存的后果不是多占几行：同一个 key 在两处可以有不同的话，
// 而用户看到哪一句取决于组件当初 import 了谁——那种不一致查起来毫无线索。
//
// 现在词条全部并进 `messages/`（zh/en 键集一致），本文件只留一个**薄转发**：
// 十个 v0.3 组件的 `import { t } from "…/lib/i18n"` 一行都不用改，
// 而它们取到的与新组件取到的是同一份。
//
// 旧签名 `t(key, locale)` 的第二个参数在仓库里实测 0 处调用；新签名第二参是插值 values。

export type { Locale } from "./i18n/config";
export { t } from "./i18n/t";
