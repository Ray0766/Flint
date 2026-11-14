"use client";

// WIRE-03：把 `Fetched<T>` 的五态渲染成屏上四种**互不相同**的东西。
//
// ## 为什么在 `web/lib/` 而不是 `web/components/shell/`
//
// 两条：① `web/components/` 不在 `WIRE-03` 的 outputs 内；
// ② **`UIX-01` 正要在 `components/shell/` 建 S1 通用件**
// （`LoadingSkeleton` / `EmptyState` / `ErrorState` / `NotFound404` /
// `SseDisconnectNotice`），现在往那儿放一个同名同职的东西必然撞车。
// 这里是**临时接缝**，`UIX-01` 落地后应当被它替掉——已在 `WIRE-03` trace 登记。
//
// ## 四种显示，四个 `data-screen-state`
//
// | state | `data-screen-state` | 说的是 |
// |---|---|---|
// | `loading` | `loading` | 正在查 |
// | `ready` | （交给子组件自己标） | 拿到了 |
// | `not_found` | `not_found`（由 `NotFound404` 自己标） | 这个能力在，这一条不存在 |
// | `not_provided` | `not_provided` | 这条路由没挂上 |
// | `not_configured` | `not_configured` | 挂上了，但背后没有库 |
// | `failed` | `failed` | 后端回了错误状态 |
//
// **`not_provided` 与 `not_configured` NEVER 合并**：前者要人去挂路由，
// 后者要人去配一个后端。合并了，读屏的人就得自己去猜是哪一种。
//
// **`not_found` 与 `not_provided` 同理，且更容易混**（`FIX-11` 接的）：
// 两者在屏上都是「你要的东西不在这儿」，而混成一句「找不到」之后，
// 用户会拿一个正确的 id 反复试；反过来混，用户会以为自己的数据被删了。

import type { JSX, ReactNode } from "react";

import { NotFound404 } from "../components/shell/NotFound404";
import { t } from "./i18n/t";
import type { Fetched } from "./screenClient";

export function ScreenFetchState<T>({
  state,
  children,
  what,
}: {
  state: Fetched<T>;
  children: (data: T) => ReactNode;
  /**
   * 找的是什么（「这份交付物」「这个项目」）。**调用方给**——各屏不一样。
   * 不给时退到一句通用的，NEVER 编一个具体名词顶上：
   * 编错了的那句话比笼统的那句更难发现。
   */
  what?: string;
}): JSX.Element {
  if (state.kind === "ready") {
    return <>{children(state.data)}</>;
  }
  if (state.kind === "loading") {
    return (
      <p className="screen__state" data-screen-state="loading">
        {t("screen.loading")}
      </p>
    );
  }
  if (state.kind === "not_configured") {
    return (
      <section className="screen__state" data-screen-state="not_configured"
        data-family={state.family}>
        <p>{t("screen.not_configured")}</p>
        <p className="screen__state-hint">{t("screen.not_configured_hint")}</p>
      </section>
    );
  }
  if (state.kind === "not_found") {
    // 后端自己的说明原样带出（`detail`）：`BE-09` 把无权与不存在收进同一条路，
    // 那句话该由它来说，NEVER 在这里改写成一句「找不到」。
    return <NotFound404 what={what ?? t("state.not_found_what")} id={state.detail} />;
  }
  if (state.kind === "failed") {
    return (
      <section className="screen__state" data-screen-state="failed"
        data-status={String(state.status)}>
        <p>{t("screen.failed")}</p>
        <p className="screen__state-hint">{t("screen.failed_hint")}</p>
        {/* 后端自己的说明原样带出来，NEVER 改写成一句通用的「出错了」 */}
        <pre className="screen__state-detail">{state.detail}</pre>
      </section>
    );
  }
  return (
    <p className="screen__state" data-screen-state="not_provided">
      {t("shell.not_provided")}
    </p>
  );
}
