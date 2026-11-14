import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

/**
 * UI-01 / S1 通用件：「接口未提供」标。
 *
 * ## 它是诚实态，不是脚手架
 *
 * FB-10 的分界原话：**A 类脚手架 = 开发要看的东西跑到了产品面**（端点路径、
 * 内部 id、`X-User-Id`）；**诚实态是产品需求，一条都不许删**——「这里本该有东西、
 * 而后端还没有」正是用户有权知道的事。所以这个标的文案 NEVER 出现端点名或字段名，
 * 只说**这一块暂时没有**。
 *
 * ## 为什么不用生成文字填上
 *
 * 蓝本 README 原话：「未建接口留位 → 取数位 + 浮层『接口未提供』，
 * **不用生成文字填**」。填上去的字与真数据长得一样，用户无从分辨——
 * 那比空着更坏。
 *
 * 形态照 `_ds` 的既有约定：虚线框 + mono 短标签，无图标字体、无 emoji。
 */
export function NotProvided({ label }: { label?: string }): JSX.Element {
  return (
    <span className="not-provided" data-not-provided="true">
      <span className="not-provided__mark" aria-hidden="true" />
      <span className="not-provided__text">{label ?? t("shell.not_provided")}</span>
    </span>
  );
}
