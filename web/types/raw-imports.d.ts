/**
 * `?raw` 导入的类型声明（FIX-03）。
 *
 * `import source from "./X?raw"` 是打包器的后缀语法：拿到的是**那个文件的原文**。
 * vitest 一直解析得好好的，缺的只是 TypeScript 这一侧的一句声明——
 * 缺了它，`npx tsc --noEmit` 每次都报 `TS2307 Cannot find module`。
 *
 * 类型恒为 `string`，NEVER 写成 `any`：
 * 两者都能让 tsc 闭嘴，但 `any` 会让 `source.split("\n")` 之后的一切失去检查，
 * **错的用法与对的用法从此长得一模一样**。判据
 * `tests/v041/test_tsc_clean.py::test_the_declaration_is_a_string_not_an_escape_hatch`
 * 真造一次误用（赋给 `number`）来钉这件事：写成 `any` 的那天它会红。
 *
 * 这里只声明 `?raw` 一种后缀。`?url` / `?inline` 之类现在没人用，
 * 用到的那天再各自声明——一次把打包器的全部后缀都声明上，
 * 等于替一批还没写的代码提前放行。
 */
declare module "*?raw" {
  const content: string;
  export default content;
}
