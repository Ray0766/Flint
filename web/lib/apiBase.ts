// demo 后端基址：本地一键 demo 走合并 ASGI 后端（uvicorn :8000）。
// NEXT_PUBLIC_FLINT_API 未设 → ""（同源，供既有测试/生产反代场景保持不变）。
export const API_BASE: string = process.env.NEXT_PUBLIC_FLINT_API ?? "";

/**
 * 调用方身份。**从配置读，NEVER 写死在组件里**（`FB-10` 的 A 类：`X-User-Id` 逐字点名在内）。
 *
 * 本仓今天还没有真的登录态——账户位一直是「接口未提供」。
 * 在那之前，写数据的端点（`POST /favorites`、`POST /shares`）需要一个身份头，
 * 它由部署配置给：**没配就不发那个头**，服务端会照实拒绝，
 * 屏上于是显示服务端自己的说明——而不是我们假装有一个用户。
 */
export const API_USER_ID: string = process.env.NEXT_PUBLIC_FLINT_USER_ID ?? "";
