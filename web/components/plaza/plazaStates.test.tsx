// PLAZA-03：规格 #2.14 的四条状态规则 —— **阴性对照逐条构造**。
//
// 「四种情况分别渲染，断言互不串台」是卡面 acceptance⑤ 的原话。
// 所以下面每一态都单独构造一次，并且**逐条断言另外三态不在场**：
// 只断言「本态在」的话，一个把四态全渲染出来的实现照样全绿。
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlazaCards } from "./PlazaCards";
import { t } from "../../lib/i18n/t";
import type { PlazaCluster } from "../../lib/viewsClient";

const REGIONS = ["AU", "CN", "JP"] as const;

const cluster = (i: number): PlazaCluster => ({
  cluster_id: `c${i}`,
  canonical_name: `热点 ${i}`,
  category_id: "cat-ai",
  status: "active",
  by_source: { weibo: 100 },
  total_heat: 100 - i,
});

/** 四态的判别位；每条断言都拿它做「另外三态不在场」的对照。 */
const STATES = ["loading", "empty", "source_outage", "ready"] as const;

function stateOf(container: HTMLElement): string | null {
  const host = container.querySelector("[data-plaza-state]");
  return host?.getAttribute("data-plaza-state") ?? null;
}

describe("PLAZA-03 广场四态", () => {
  it("加载中 → 骨架卡，不是一行「加载中」文字", () => {
    const { container } = render(<PlazaCards clusters={null} />);

    expect(stateOf(container)).toBe("loading");
    // 骨架**是卡片形状的**：借的是同一个 .hotspot-card 卡壳。
    const skeletons = container.querySelectorAll(".hotspot-card--skeleton");
    expect(skeletons.length).toBeGreaterThan(1);
    expect(container.querySelector("[data-plaza-skeleton], [data-testid='plaza-skeleton']"))
      .not.toBeNull();
    expect(container.querySelector("[aria-busy='true']")).not.toBeNull();
  });

  it("加载中 NEVER 同时出现空态话术——「还没查」不是「查过了没有」", () => {
    render(<PlazaCards clusters={null} regions={REGIONS} />);

    expect(screen.queryByText(t("plaza.empty.no_data_today"))).toBeNull();
    expect(screen.queryByTestId("plaza-empty")).toBeNull();
    expect(screen.queryByTestId("plaza-outage-badge")).toBeNull();
  });

  it("空结果 → 「该区当日无数据」并列出可切换的区", () => {
    const { container } = render(
      <PlazaCards clusters={[]} region="CN" regions={REGIONS} />,
    );

    expect(stateOf(container)).toBe("empty");
    expect(screen.getByText(t("plaza.empty.no_data_today"))).not.toBeNull();
    const listed = [...container.querySelectorAll("[data-region]")]
      .map((el) => el.getAttribute("data-region"));
    expect(listed).toEqual(["AU", "JP"]);        // 当前区不重复列出
  });

  it("空结果 NEVER 回落到别的区假装有数据", () => {
    const { container } = render(
      <PlazaCards clusters={[]} region="CN" regions={REGIONS} />,
    );

    // 一张卡都不许出现——「别的区有」不是「这个区有」。
    expect(container.querySelectorAll("[data-testid='hotspot-card']")).toHaveLength(0);
    expect(container.querySelector("[data-plaza-stack]")).toBeNull();
    expect(container.querySelector("[data-plaza-list]")).toBeNull();
  });

  // 这条判据**改过一次**，改因记在这里。
  //
  // 改前它断言空态里有一句「地区切换还没接通」。那句话在 PLAZA-03 当时是实话：
  // `GET /plaza/hot` 只收 `day`。`REGION-09/10` 之后端点真的筛了、开关也上了屏，
  // 那句话变成**假话**——留着假话比没有提示更坏：它会让用户不去用一个能用的东西。
  //
  // 空态本身的纪律**一个字没松**：仍然只列出别的区、仍然 NEVER 回落到别的区
  // 假装有数据（规格 #2.14 的原话）。切换控件在屏顶（`RegionSwitch`），
  // 不在空态里——**空态 NEVER 自己再长一个控件出来**：同一件事两个入口，
  // 两处的状态迟早对不上。
  it("空态只列出别的区，NEVER 自己再长一个切换控件", () => {
    render(<PlazaCards clusters={[]} region="CN" regions={REGIONS} />);

    expect(screen.queryByTestId("plaza-switch-not-wired")).toBeNull();
    expect(screen.getByTestId("plaza-empty-regions")).not.toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
  });

  it("没查到地区清单时不编一份出来（LOC-01：清单只有一处真相）", () => {
    render(<PlazaCards clusters={[]} region={null} regions={null} />);

    expect(screen.getByText(t("plaza.empty.no_data_today"))).not.toBeNull();
    expect(screen.queryByTestId("plaza-empty-regions")).toBeNull();
  });

  it("单区源全灭 → 缺数据角标，且**其余照常渲染**", () => {
    const { container } = render(
      <PlazaCards clusters={[cluster(0), cluster(1)]} sourceOutage region="CN" />,
    );

    expect(stateOf(container)).toBe("source_outage");
    expect(screen.getByTestId("plaza-outage-badge").textContent)
      .toBe(t("plaza.badge.source_outage"));
    // 把内容藏起来等于用一次降级抹掉所有还好的部分。
    expect(container.querySelectorAll("[data-plaza-list] [data-cluster-id]"))
      .toHaveLength(2);
  });

  it("源全灭与空结果 NEVER 共用一个表示", () => {
    const outage = render(
      <PlazaCards clusters={[cluster(0)]} sourceOutage />,
    ).container;
    const empty = render(<PlazaCards clusters={[]} />).container;

    expect(stateOf(outage)).not.toBe(stateOf(empty));
    expect(outage.querySelector("[data-testid='plaza-empty']")).toBeNull();
    expect(empty.querySelector("[data-testid='plaza-outage-badge']")).toBeNull();
  });

  it("有数据 → ready，四态判别位互不重复", () => {
    const rendered = {
      loading: render(<PlazaCards clusters={null} />).container,
      empty: render(<PlazaCards clusters={[]} />).container,
      source_outage: render(<PlazaCards clusters={[cluster(0)]} sourceOutage />).container,
      ready: render(<PlazaCards clusters={[cluster(0)]} />).container,
    };

    for (const state of STATES) {
      expect(stateOf(rendered[state])).toBe(state);
    }
  });

  it("译名缺失只显 name_native 单行（A7），NEVER 用原文冒充译文", () => {
    render(<PlazaCards clusters={[cluster(0)]} />);

    expect(screen.getAllByTestId("native-primary")[0].textContent).toBe("热点 0");
    expect(screen.queryAllByTestId("native-secondary")).toHaveLength(0);
    expect(screen.queryAllByTestId("native-mt-mark")).toHaveLength(0);
  });

  it("源全灭的默认值是 false —— 后端还没有这个信号，行为与今天逐字相同", () => {
    const { container } = render(<PlazaCards clusters={[cluster(0)]} />);

    expect(container.querySelector("[data-testid='plaza-outage-badge']")).toBeNull();
    expect(stateOf(container)).toBe("ready");
  });
});
