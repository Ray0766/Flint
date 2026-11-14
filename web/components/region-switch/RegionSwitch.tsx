// I18N-08：地区切换（切区不改语言）。
//
// PRINCIPLES#A3：语言与地区**正交**。切 region 只做两件事——
// 写偏好、刷新热点集合；**NEVER 顺手改 locale**。
//
// ## 清单不在这里（LOC-01）
//
// 这里原先写着一份九区数组，而真相在 `contracts_v04.Region`，
// `DEC-056` 加 HK 那天真相变成十项，而**这里什么都不用改**——那正是搬走副本换来的。
// `GET /settings/locale` 的 `options.region` 就是它。**两份清单迟早各说各的**：
// 加第十个地区那天只有一处会跟上，而读的人分不出哪份是真的。
// 所以清单改由调用方从端点取来、当 `regions` 传进来。
//
// 联合类型 `Region` 一起退役——`type Region = "…" | "…"` 与那个数组一样是副本，
// 加第十个地区那天 `tsc` 会理直气壮地拦下新地区。这里用 `string`：
// **可选值由后端把关**（`PUT /settings/locale` 对不在 options 里的值回 422），
// 前端再拦一道就是把同一条规则写第二遍。
//
// 「无 EU（EU 是区域联盟，不是地区）」那句断言没有消失，它搬去了源头——
// `tests/v041/test_regions_from_backend.py` 在真栈上判 `options.region`。
// 从前它判的是一份抄件。
//
// ## 拿不到清单时 NEVER 渲染一个空 `<select>`
//
// 空下拉读起来是「没有可选地区」，那是一句结论；真相是「这份清单没查到」。
// 所以这里如实标未提供态，与 `ScreenFetchState` 用同一个 `data-screen-state`。

import type { JSX } from "react";

import { t } from "../../lib/i18n/t";
import { regionOptionLabel } from "../../lib/regions";

export type RegionSwitchProps = {
  region: string;
  /** 可选地区清单：来自 `GET /settings/locale` 的 `options.region`。
   *  `null` 或空 = **没查到**，NEVER 用一份自带的清单顶上。 */
  regions: readonly string[] | null;
  /** 当前语言。只用于**显示**，切区时原样带回——NEVER 由 region 推导。 */
  lang: string;
  /** 切区回调：调用方负责写服务端偏好并刷新热点集合。 */
  onChange: (next: { region: string; lang: string }) => void;
  /** 这一处的记号。**默认是既有那个值**，所以既有判据一条都不用改。
   *
   *  `SHELL-01` 之后屏上同时有两个 `RegionSwitch`：顶栏那个写的是**服务端偏好**
   *  （跨设备、跨屏），广场那个驱动的是**这一屏的筛选**（`?region=`）。
   *  两者意思不同却共用一个 `data-testid`，于是任何判据都分不出自己打的是哪一个——
   *  `CN-02` 取证时实测到：一次 `option` 扫描回了 19 项（两个 select 的并集）。
   *  给顶栏那个换一个记号，两处从此可分辨。 */
  testId?: string;
};

export function RegionSwitch({
  region,
  regions,
  lang,
  onChange,
  testId = "region-select",
}: RegionSwitchProps): JSX.Element {
  if (regions === null || regions.length === 0) {
    return (
      <p
        className="region-switch"
        data-testid="region-switch"
        data-screen-state="not_provided"
        data-lang={lang}
      >
        {t("shell.not_provided")}
      </p>
    );
  }
  return (
    <label className="region-switch" data-testid="region-switch" data-lang={lang}>
      <span data-testid="region-switch-label">{t("settings.region.label")}</span>
      <select
        data-testid={testId}
        value={region}
        onChange={(e) => {
          // lang 原样带回：切区 NEVER 改语言（A3）
          onChange({ region: e.target.value, lang });
        }}
      >
        {/* REGION-11：地区码**原样显示**，未归区走文案。
            `unassigned` 是内部记号，印在屏上就是 `FB-10` 点名的
            **A 类脚手架：开发要看的东西跑到了产品面**。
            文案本身要说清「它不是一个地理区」——只写三个字的话，
            它排在九个国家代码旁边，读起来像第十个国家。 */}
        {regions.map((r) => (
          <option key={r} value={r}>
            {regionOptionLabel(r)}
          </option>
        ))}
      </select>
    </label>
  );
}
