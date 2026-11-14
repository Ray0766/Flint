"use client";

import { useState, type JSX } from "react";

import { LANGS } from "../locale-settings/LocaleSettings";
import { RegionSwitch } from "../region-switch/RegionSwitch";
import { t } from "../../lib/i18n/t";
import { useScreenData } from "../../lib/useScreenData";
import { putLocaleAxis, type LocaleAxis, type LocaleResponse } from "./localeClient";

/**
 * SHELL-01 / `DEC-046`：顶栏右上角的地区与语言下拉。
 *
 * owner 2026-08-09 原话：「**地区和语言做到页面右上角，直接下拉选择**」。
 *
 * ## 这是**新增**，不是搬家
 *
 * 卡面写「当前两者只在 `/settings/locale` 那一屏里」。实查不是：
 * `LocaleSettings` 只在那一屏，而 `RegionSwitch` **在广场页上另有一个实例**
 * （`web/app/plaza/page.tsx`，它按 `?region=` 驱动热点集合）。
 * 真相是**外壳右上角两者都没有**——那才是 owner 说的那件事。
 *
 * 所以本组件是第三处，而**三处共用同一个值**：都读
 * `GET /settings/locale`，写都走 `PUT /settings/locale`。
 * 各存一份的话，用户在右上角切了区、进详情屏看到的还是旧的，
 * 而**两个真相长得一模一样**，谁也说不出哪个是对的。
 *
 * ## 两条轴各自独立（`PRINCIPLES#A3`）
 *
 * **切地区 NEVER 改语言，切语言 NEVER 改热点集合。**
 * 挪位置这个动作最容易顺手把两者并成一个「区域设置」控件——
 * 并了之后，**一个说中文的人想看美国区的热点就没法表达了**。
 *
 * 落地形态：两个独立的 `<select>`，`onChange` 各自只发自己那一根轴
 * （`putLocaleAxis`），后端 `set_prefs` 也只改传进来的那一项。
 *
 * ## 复用既有件，NEVER 另写一份
 *
 * 地区那一格直接用 `RegionSwitch`（它自带「清单没查到就如实标未提供态」
 * 与地区码显示口径）；语言那一格的可选值用 `LocaleSettings` 导出的 `LANGS`。
 * 九区清单仍从 `GET /settings/locale` 的 `options.region` 取（`LOC-01`：一处真相）。
 *
 * ## 取数没回来之前 NEVER 显示一个猜出来的值
 *
 * 加载中就说加载中。先渲染一个 `zh/CN` 再被真值替换的话，屏上会闪一下——
 * 而那一下里用户看到的是**一个他没选过的地区**，他可能正照着它做判断。
 */

type Status = "idle" | "saving" | "error";

export function LocaleControls(): JSX.Element {
  const { state, refetch } = useScreenData<LocaleResponse>("/settings/locale");
  const [status, setStatus] = useState<Status>("idle");

  if (state.kind !== "ready") {
    // 四态照旧归取数件说（`ScreenFetchState` 的同一套口径），
    // 这里只把「还没有值可选」如实标出来。
    return (
      <div
        className="app-shell__locale"
        data-testid="shell-locale"
        data-screen-state={state.kind}
      >
        <span className="app-shell__locale-pending">{t("shell.not_provided")}</span>
      </div>
    );
  }

  const write = (axis: LocaleAxis, value: string): void => {
    setStatus("saving");
    void putLocaleAxis(axis, value)
      .then(() => {
        setStatus("idle");
        // 回读服务端那份：屏上显示的恒是**库里认下的值**，
        // 而不是本地乐观改出来的那个。
        refetch();
      })
      .catch(() => {
        // 保留用户的选择 + 说清楚失败了，NEVER 回滚成旧值假装成功。
        setStatus("error");
      });
  };

  return (
    <div
      className="app-shell__locale"
      data-testid="shell-locale"
      data-screen-state="ready"
      data-locale-status={status}
    >
      {/* 地区：复用 `RegionSwitch`。`lang` 原样带回——切区 NEVER 改语言。 */}
      <RegionSwitch
        // 与广场那个 `RegionSwitch` 分开记号：两者意思不同（这一处写服务端偏好，
        // 广场那处驱动本屏筛选），共用一个记号会让判据分不出自己打的是哪一个。
        testId="shell-region-select"
        region={state.data.region}
        regions={state.data.options.region}
        lang={state.data.lang}
        onChange={(next) => write("region", next.region)}
      />

      {/* 语言：独立的一根轴，切它 NEVER 碰 region。 */}
      <label className="app-shell__locale-lang" data-testid="shell-lang">
        <span data-testid="shell-lang-label">{t("locale.lang")}</span>
        <select
          data-testid="shell-lang-select"
          data-locale-axis="lang"
          value={state.data.lang}
          disabled={status === "saving"}
          onChange={(e) => write("lang", e.target.value)}
        >
          {LANGS.map((code) => (
            <option key={code} value={code}>{t(`locale.lang.${code}`)}</option>
          ))}
        </select>
      </label>

      {status === "error" ? (
        <span className="app-shell__locale-error" data-locale-error="true">
          {t("locale.save_failed")}
        </span>
      ) : null}
    </div>
  );
}
