import type { JSX, ReactNode } from "react";

import "./globals.css"; // FB-01：把 _ds 接进应用。此前这里零 CSS import —— 终检 F-09 的根因
import { AppShell } from "../components/shell/AppShell";
import { DS_BUNDLE_SRC, DsBundleMount } from "../components/shell/dsBundle";
import { t } from "../lib/i18n/t";

// 站点标题也是界面文案：写死在这里的话，切英文时浏览器标签页仍是中文，
// 而那是用户第一眼看到的东西。
export const metadata = {
  title: t("app.title"),
  description: t("app.description"),
};

export default function RootLayout({
  children,
}: {
  children: ReactNode;
}): JSX.Element {
  return (
    <html lang="zh-CN">
      <head>
        {/* FB-01：_ds 是供应商资产，留在 public/ 里按 URL 取，NEVER 搬进构建面。
            从 globals.css 里 @import 这条 URL 会在构建时报 Module not found（实测整页 500），
            因为那是运行时路径不是模块路径。路径里的哈希段随导出包变，
            tests/v041/test_ds_wired.py 盯着它必须解析得到真文件——写错的路径静默 404，
            页面照样渲染、只是没有样式，那正是 F-09 的形状。 */}
        <link
          rel="stylesheet"
          href="/_ds/flint-design-system-8fd95ba3-cf31-49b6-b9d8-c863f3dc2724/styles.css"
        />
        {/* DS-01：**CSS 那一半 FB-01 接了，JS 这一半从没接过**——`StickerTag` 与
            `StatusMark` 就在 `_ds_bundle.js` 里，全仓零引用。

            这里只做预取，真正的插入在 `DsBundleMount`（客户端）里：bundle 读的是
            全局 `React`，必须先把应用这一份 React 喂上去再执行脚本，
            顺序倒了它会在自己的 try/catch 里静静失败——页面不报错、组件不存在。
            预取是为了让那一步几乎不花时间，卡片不会先秃一帧。 */}
        <link rel="preload" as="script" href={DS_BUNDLE_SRC} />
      </head>
      {/* UI-01：S0 外壳（顶栏 wordmark + 导航 + 账户位）包住每一屏。
          放在 layout 而不是逐屏各写一份——各写一份的话，改一处顶栏要改 N 个文件，
          而漏掉的那一屏在界面上长得像另一个产品。 */}
      <body>
        <DsBundleMount />
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
