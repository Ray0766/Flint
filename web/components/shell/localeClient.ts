// SHELL-01：把一根轴写回服务端（`PUT /settings/locale`）。
//
// ## 为什么这个文件在 `components/shell/` 而不是 `web/lib/`
//
// 它的自然归宿是 `web/lib/`（`jobClient` / `topicClient` / `derefClient` 都在那儿）。
// **本卡的 outputs 只有 `web/components/shell/` 与它的判据文件**，
// 而本批 rules 写死「改动面大于卡上 outputs → 停下走 `docs/blocked/`」。
// 为一个文件停下一张卡不成比例，把它塞进 outputs 之内也不该悄悄发生——
// 所以放在这里并**在这里写明**：它该搬去 `web/lib/localeClient.ts`，
// 搬家由后续任一张 outputs 含 `web/lib/` 的卡顺手做，`docs/trace/SHELL-01.md` 记着这件事。
//
// ## 一次只写一根轴
//
// `PRINCIPLES#A3`：语言只统治 UI 文案与生成内容语言，地区只决定数据源选集与
// 热点集合。后端 `set_prefs` 的口径是「**只改传进来的那一项**」，
// 所以这里也**只发改动的那一根**——两根一起发的话，用户切地区时会把语言
// 也原样写一次，而那次写入会把另一个设备上刚改的语言覆盖掉。
//
// ## 失败不回滚，也不假装成功
//
// 写失败时把错误交出去，由调用方保留用户的选择并显示错误
// （`LocaleSettings` 文件头的既有口径：「保留用户选择并显示错误，
// NEVER 回滚成旧值假装成功」）。回滚之后屏上是旧值、没有报错，
// 用户会以为自己没点到——他会再点一次，然后再失败一次。

import { API_BASE, API_USER_ID } from "../../lib/apiBase";

// `SHELL-02` 加了第三根轴。三根**互不牵动**——一次仍然只发一根。
export type LocaleAxis = "lang" | "region" | "theme";

export type LocaleResponse = {
  lang: string;
  region: string;
  /** `SHELL-02` 加的第三根轴。**可选**：老录制回放夹具里没有这一格，
   *  声明成必填会让那些夹具全部失效。缺席时按「跟随系统」处理。 */
  theme?: string;
  options: { lang: string[]; region: string[]; theme?: string[] };
};

/** 写回一根轴。成功回服务端那份（**不是请求里那份**）；失败抛。 */
export async function putLocaleAxis(
  axis: LocaleAxis,
  value: string,
  opts: { baseUrl?: string; userId?: string; fetchImpl?: typeof fetch } = {},
): Promise<LocaleResponse> {
  const f = opts.fetchImpl ?? fetch;
  const headers: Record<string, string> = { "content-type": "application/json" };
  const userId = opts.userId ?? API_USER_ID;
  // 没配身份就不发这个头——**NEVER 编一个身份**（`derefClient` 的同一条口径）。
  if (userId) headers["x-user-id"] = userId;

  const res = await f(`${opts.baseUrl ?? API_BASE}/settings/locale`, {
    method: "PUT",
    headers,
    // 只放改动的那一根轴（见文件头）。
    body: JSON.stringify({ [axis]: value }),
  });
  if (!res.ok) {
    // **错误里 NEVER 带端点路径**：`tools/no_scaffold_on_screen.mjs` 把
    // 端点路径列进「A 类脚手架」——它是开发要看的东西，
    // 而 `Error.message` 随时可能被某一屏渲染出来（本卡实测被那把尺子拦下）。
    // 状态码留着：它是调用方分辨「拒绝」与「挂了」的唯一依据，且不泄露内部结构。
    throw new Error(String(res.status));
  }
  // 回的是**库里那份**：服务端可能把它规范化过，屏上要显示它认下的那个值。
  return (await res.json()) as LocaleResponse;
}
