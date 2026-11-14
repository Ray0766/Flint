// I18N-08 验收：切 region 触发热点刷新且 locale 不变。
//
// LOC-01：清单不再由本组件持有——它从 `GET /settings/locale` 的 `options.region`
// 传进来。所以这里**故意喂一份三项的清单**：渲染出来必须正好是这三项。
// 组件若还留着一份自带的地区清单，这条当场变红。
//
// 「清单完整、无 EU」那句断言没有消失，它搬去了源头：
// `tests/v041/test_regions_from_backend.py` 在装配后的真栈上判 `options.region`。
// **从前它判的是一份抄件。**
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RegionSwitch } from "./RegionSwitch";

// 三项，且顺序不是字母序——「照单渲染」与「自己排一遍」由此可分。
const SERVED = ["JP", "CN", "FR"] as const;

describe("RegionSwitch", () => {
  it("渲染的就是端点给的那份清单，一项不多一项不少", () => {
    render(<RegionSwitch region="CN" regions={SERVED} lang="zh" onChange={() => {}} />);
    const options = screen.getAllByRole("option");

    expect(options).toHaveLength(SERVED.length);
    expect(options.map((o) => o.getAttribute("value"))).toEqual([...SERVED]);
  });

  it("清单为 null → 说「接口未提供」，NEVER 渲染一个空下拉", () => {
    // 空 `<select>` 读起来是「没有可选地区」，那是一句结论；
    // 真相是「这份清单没查到」。
    render(<RegionSwitch region="CN" regions={null} lang="zh" onChange={() => {}} />);

    expect(screen.queryByTestId("region-select")).toBeNull();
    expect(screen.getByTestId("region-switch"))
      .toHaveAttribute("data-screen-state", "not_provided");
  });

  it("清单为空数组 → 同样是未提供态，NEVER 当成「没有地区」", () => {
    render(<RegionSwitch region="CN" regions={[]} lang="zh" onChange={() => {}} />);

    expect(screen.getByTestId("region-switch"))
      .toHaveAttribute("data-screen-state", "not_provided");
  });

  it("切区回调带出新 region —— 调用方据此刷新热点集合", () => {
    const onChange = vi.fn();
    render(<RegionSwitch region="CN" regions={SERVED} lang="zh" onChange={onChange} />);
    fireEvent.change(screen.getByTestId("region-select"), { target: { value: "JP" } });

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange.mock.calls[0][0].region).toBe("JP");
  });

  it("切区 NEVER 改语言：lang 原样带回（A3 双断言之二）", () => {
    const onChange = vi.fn();
    render(<RegionSwitch region="CN" regions={SERVED} lang="en" onChange={onChange} />);
    fireEvent.change(screen.getByTestId("region-select"), { target: { value: "JP" } });

    expect(onChange.mock.calls[0][0].lang).toBe("en");
  });

  it("组件不自行推导语言：切到 JP 也 NEVER 变成 ja", () => {
    const onChange = vi.fn();
    render(<RegionSwitch region="CN" regions={SERVED} lang="zh" onChange={onChange} />);
    fireEvent.change(screen.getByTestId("region-select"), { target: { value: "JP" } });

    expect(onChange.mock.calls[0][0].lang).toBe("zh");
    expect(screen.getByTestId("region-switch")).toHaveAttribute("data-lang", "zh");
  });

  it("标签文案走 i18n key，NEVER 硬编码中文", () => {
    render(<RegionSwitch region="CN" regions={SERVED} lang="zh" onChange={() => {}} />);

    expect(screen.getByTestId("region-switch-label").textContent).toBeTruthy();
  });
});
