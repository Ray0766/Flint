// DESIGN-02：设计台渲染管线（G10，`iframe.srcdoc` 直挂、零构建）。
//
// **零构建**：生成的 HTML 原样挂进 `srcdoc`，不转译、不打包。转译一遍等于让
// 预览与最终产物**不是同一份东西**——用户在预览里调好的样子，导出时可能因为
// 转译差异变形，而他无从知道是哪一步动了手脚。srcdoc 直挂时，预览里那段字节
// 就是最终那段字节。
//
// **安全靠沙箱，不靠改写内容**：srcdoc 里的东西是模型生成的，里面出现 `fetch`
// 或 `<script>` 是完全正常的（模型见过无数带它们的示例）。正确的做法是把它关进
// 沙箱，而不是偷偷把这些片段删掉——删掉会制造「预览与产物不一致」，
// 而那正是零构建要避免的事。
//
// **沙箱标志显式列出**：`allow-same-origin` 与 `allow-scripts` 同时给，等于沙箱形同虚设
// （里面的脚本能自己把沙箱摘掉）。这里只给最小集合，且有测试逐项盯着。

import type { JSX } from "react";

import { t } from "../../lib/i18n/t";

/** 最小沙箱集合：允许脚本跑起来（预览要能动），但不给同源、不给顶层跳转。 */
export const SANDBOX_FLAGS = ["allow-scripts", "allow-forms"] as const;

export function SrcdocRenderer({ html }: { html: string }): JSX.Element {
  return (
    <iframe
      data-testid="design-srcdoc-frame"
      title={t("design.renderer.title")}
      sandbox={SANDBOX_FLAGS.join(" ")}
      srcDoc={html}
    />
  );
}
