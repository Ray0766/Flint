# FAV-06 trace — 图书馆空态（引导去广场）@2026-08-03

## 1 verify
`cd web && npm test -- --run views/library-empty` → **4 passed**；
前端全套 134 passed / 22 files；typecheck 干净；`i18n_scan` exit 0。

## 2 空态不是错误态
没有收藏是**新用户的正常起点**。所以给的是一条**出路**（可点的广场链接），
而不是一句「暂无数据」——后者把用户留在原地。
`空态给的是出路而不是「暂无数据」` 一条断言 CTA 必须是可点的 `<a href>`。

## 3 测试抓到一个真实缺失
`两条文案都取到了内容` 断言文案**不等于 key 本身**——因为 `t()` 在 key 缺失时
回落成 key 原样。首轮红：`library.empty` 这个 key **在 messages 里不存在**
（它只写在 `docs/前端功能说明-v2.md` 的 key 总表里，没落进 json）。
补齐后 zh/en 各 17 key、键集一致。

**这条断言的价值正在于此**：只断言「文案非空」会绿——因为回落值 `library.empty` 也非空。

## 4 路由常量单一来源
`PLAZA_ROUTE = "/plaza"` 导出为常量，NEVER 各处各写一个字符串。

## 5 产出
`web/views/library-empty/LibraryEmpty.tsx`、`LibraryEmpty.test.tsx`（4 条）、
`web/messages/{zh,en}.json` 补 3 key。
