"use client";

import { useEffect, useState, type JSX } from "react";

import { LocaleSettings, type LocaleDraft } from
  "../../../components/locale-settings/LocaleSettings";
import { putLocaleAxis } from "../../../components/shell/localeClient";
import { Screen } from "../../../components/shell/Screen";
import { ScreenFetchState } from "../../../lib/ScreenFetchState";
import { useScreenData } from "../../../lib/useScreenData";
import { t } from "../../../lib/i18n/t";

// UI-07 / v2 屏 2.13：语言与地区设置。
//
// 风格来源：`Claude design Flint 前端设计/Flint 应用 · 20 屏/
// Flint 批次一 · 外壳与入口.dc.html` 的表单形态。
//
// ## 端点状态
//
// v2 2.13 写的是 `GET/PATCH /me/preferences`【未建·接口预留】。
// BE-07 本轮把这件事做出来了，但**路径不同**：`GET/PUT /settings/locale`
// （`flint/api/settings.py`）。而且它**没挂进 `flint/api/app.py`**——
// AUDIT-01 对账表里的「未装配」。
//
// 所以这一屏此刻读不到已存的偏好：`saved` 传 `null`（**没查过**），
// 屏上显示声明过的默认值并标「未保存」——这正是 v2 对「无 profile」的要求，
// 且 NEVER 用浏览器语言去猜。
//
// `WIRE-01` 把 `GET /settings/locale` 挂上了，本屏改为真取数。
//
// **这一屏的「空」不是假话**：没存过偏好时后端回的是**声明过的默认值**
// （实测 `{"lang":"zh","region":"CN","options":{...地区清单...}}`），
// 而「查过了、你没改过设置」与「默认值就是当前值」是同一件事。
// 其余几族的空是内存件的空，那才是假话——见
// `docs/blocked/WIRE-03-EMPTY-FROM-A-STORE-THAT-HAS-NO-DATABASE.md`。
//
// 草稿仍从**声明过的默认值**起步，取回来之后再对齐，NEVER 从浏览器猜。
//
// ## LOCALE-SAVE：这一屏此前**存不了**
//
// 改前这里写着 `status="idle"` 这个**字面量**，且**没有传 `onSave`**——
// 组件早就备好了 `onSave?` 与三态，缺的只是页面这一半。
// 屏上的效果是：按钮在，按下去**什么都不会发生**，
// 而用户会以为自己没点到（组件文件头那句话说的正是这个）。
//
// ### 只发**改过的**那根轴
//
// 写回走 `putLocaleAxis`（`SHELL-01` 建的那一个，右上角三根轴用的也是它）——
// **一处定义他处引用**，NEVER 在这里新写一份 fetch：两份写法会各自漂移，
// 而漂移的那一天，右上角与这一屏存的就不是同一份 `prefs` 了。
//
// 两根轴都没改就不发（A3 正交，后端 `set_prefs` 的口径是「只改传进来的那一项」）：
// 原样回写一次的话，会把另一台设备上刚改的那根轴覆盖掉。
//
// ### 失败 NEVER 回滚
//
// 保留用户的选择并显示错误。回滚之后屏上是旧值、没有报错，
// 用户会以为自己没点到——**他会再点一次，然后再失败一次**。
const DEFAULTS: LocaleDraft = { lang: "zh", region: "CN" };

type LocaleResponse = {
  lang: string;
  region: string;
  options: { lang: string[]; region: string[] };
};

export default function LocaleSettingsPage(): JSX.Element {
  const { state } = useScreenData<LocaleResponse>("/settings/locale");
  const [draft, setDraft] = useState<LocaleDraft>(DEFAULTS);
  const [status, setStatus] = useState<"idle" | "saving" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const saved: LocaleDraft | null =
    state.kind === "ready" ? { lang: state.data.lang, region: state.data.region } : null;

  useEffect(() => {
    // 取回来之后把草稿对齐一次；此后用户的每一次改动都归用户。
    if (state.kind === "ready") {
      setDraft({ lang: state.data.lang, region: state.data.region });
    }
  }, [state.kind, state.kind === "ready" ? state.data.lang : "",
      state.kind === "ready" ? state.data.region : ""]);

  async function save(): Promise<void> {
    setStatus("saving");
    setError(null);
    try {
      for (const axis of ["lang", "region"] as const) {
        // 只发改过的那一根：没改的原样回写会覆盖另一台设备上刚改的值。
        if (saved === null || draft[axis] !== saved[axis]) {
          await putLocaleAxis(axis, draft[axis]);
        }
      }
      setStatus("idle");
    } catch (err) {
      // **NEVER 回滚 `draft`**：保留用户的选择并显示错误。
      setStatus("error");
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <Screen title={t("locale.title")} meta={t("locale.meta")}>
      <ScreenFetchState state={state}>
        {(data) => (
      <LocaleSettings
        saved={saved}
        // 地区清单从响应里下发，NEVER 由前端自带一份（LOC-01）。
        regions={data.options.region}
        draft={draft}
        status={status}
        error={error}
        onSave={() => {
          void save();
        }}
        onChange={(axis, value) =>
          // 一次只动一根轴（A3 正交）：另一根原样带过去，不重新计算。
          setDraft((prev) => ({ ...prev, [axis]: value }))
        }
      />
        )}
      </ScreenFetchState>
    </Screen>
  );
}
