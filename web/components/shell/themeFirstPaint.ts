// SHELL-02 acceptance⑥：**首帧 NEVER 闪白再变暗**。
//
// ## 为什么这件事需要一段在首帧之前跑的脚本
//
// 主题的真相在服务端（`prefs.theme`，`DEC-050`）。而取那份真相要一次网络往返——
// **往返回来之前浏览器已经画完第一帧了**。用户显式选了「夜间」的话，
// 那一帧是白的，然后突然变暗：那正是 acceptance⑥ 逐字禁掉的东西。
//
// 「跟随系统」那一态**没有这个问题**：`DARK-01` 的 `prefers-color-scheme` 通道
// 是纯 CSS，浏览器在第一帧就知道该用哪套色。所以要抢在首帧之前决定的，
// **只有「显式选了亮或暗」这一种**。
//
// ## cookie 是**提示**，不是第二个真相
//
// 这里存的那个 cookie 只回答一个问题：「上一次这台设备上，这个人显式选了什么」。
// 它由**写服务端的同一段代码**顺手写下（`ThemeControl.write`），
// 并在服务端那份到手时**被服务端纠正**（`ThemeControl` 的那个 effect）。
//
// 所以两者不会长期分叉，而**分叉时服务端赢**。
//
// **NEVER 把它当成存储**：清掉 cookie 之后，用户的选择仍然在库里、换台设备也还在——
// 丢的只是「首帧不闪」这一个优化。这正是「提示」与「真相」的分界线：
// 提示丢了只是慢一点，真相丢了是数据没了。
//
// （`SHELL-01` 的判据禁掉了 `localStorage` / `sessionStorage` 存**偏好**——
// 那条禁的是「把偏好存在浏览器里当真相」。这里存的是渲染提示，
// 且服务端那份仍然是唯一被写入与被读回的偏好。）

/** cookie 名。**一处定义**：首帧脚本与控件都从这里取（判据把两处比对）。 */
export const THEME_COOKIE = "flint_theme_hint";

/** 三态里**不需要 `data-theme`** 的那一个（见 `ThemeControl` 的表）。 */
export const FOLLOW_SYSTEM = "system";

/**
 * 把选择落到 `<html>` 上。
 *
 * 「跟随系统」= **移除属性**，NEVER 写 `data-theme="system"`——
 * 那两条 CSS 规则一条都不匹配，看起来像亮色，而系统切暗时它不会变。
 */
export function applyTheme(choice: string): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  if (choice === FOLLOW_SYSTEM) {
    root.removeAttribute("data-theme");
    return;
  }
  root.setAttribute("data-theme", choice);
}

/** 记下首帧提示。**一年**：它只是提示，过期了最坏也就是闪一次。 */
export function rememberThemeHint(choice: string): void {
  if (typeof document === "undefined") return;
  document.cookie =
    `${THEME_COOKIE}=${encodeURIComponent(choice)}; path=/; max-age=31536000; SameSite=Lax`;
}

/**
 * 首帧那一段。**同步执行**，插在 `<body>` 最前面（`AppShell` 渲染它）。
 *
 * 写成字符串而不是一个函数：它要作为 `<script>` 的内容被**服务端渲染出去**，
 * 在浏览器解析到它的那一刻就跑完——比 React 水合早，也比第一帧早。
 *
 * 里面 NEVER 抛：一段在首帧之前跑的脚本抛错会把后面的解析也带停，
 * 而它做的只是一个优化。取不到 cookie 就什么都不做，让 CSS 的系统通道接管。
 */
export const THEME_FIRST_PAINT_SNIPPET = `(function(){try{
var m=document.cookie.match(/(?:^|; )${THEME_COOKIE}=([^;]*)/);
if(!m){return}
var v=decodeURIComponent(m[1]);
if(v==='light'||v==='dark'){document.documentElement.setAttribute('data-theme',v)}
}catch(e){}})();`;
