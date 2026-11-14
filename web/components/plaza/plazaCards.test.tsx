// PLAZA-01：广场卡片的交互判据（结构与运行时样式在 `tests/v041/test_plaza_cards.py`）。
//
// 这一份**接住了退役的 `PlazaView` 那两条**：列簇按后端序、空态说空态。
// 退役 NEVER 等于把判据一起删掉——那样「换了个更好看的广场」与
// 「换了个不干活的广场」在测试上长得一模一样。
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { PlazaCards } from "./PlazaCards";
import { clusterToCard } from "./clusterToCard";
import { t } from "../../lib/i18n/t";
import type { PlazaCluster } from "../../lib/viewsClient";

const cluster = (i: number): PlazaCluster => ({
  cluster_id: `c${i}`,
  canonical_name: `热点 ${i}`,
  category_id: "cat-ai",
  status: "active",
  by_source: { weibo: 100 },
  total_heat: 100 - i,
});

const CLUSTERS = [0, 1, 2, 3, 4, 5, 6].map(cluster);

describe("PlazaCards 广场", () => {
  it("列簇顺序原样照后端，本屏零排序（接住列表版广场退役前的判据）", () => {
    const { container } = render(<PlazaCards clusters={CLUSTERS} />);

    const ids = [...container.querySelectorAll("[data-plaza-list] [data-cluster-id]")]
      .map((el) => el.getAttribute("data-cluster-id"));
    expect(ids).toEqual(CLUSTERS.map((c) => c.cluster_id));
  });

  it("空结果说空态，NEVER 画一个空堆叠（接住列表版广场退役前的判据）", () => {
    const { container } = render(<PlazaCards clusters={[]} />);

    // PLAZA-03 把这句换成规格 #2.14 的原话「该区当日无数据」——**语义没变**：
    // 查过了、这一区当日没有。判据跟着换文案，NEVER 跟着换语义。
    expect(screen.getByText(t("plaza.empty.no_data_today"))).not.toBeNull();
    expect(container.querySelector("[data-plaza-stack]")).toBeNull();
  });

  it("卡面只有一份：堆叠与网格渲染的是同一个组件", () => {
    const { container } = render(<PlazaCards clusters={CLUSTERS} />);

    // 堆叠里 5 张（精选）+ 网格里 7 张（全量）= 12 张卡面，全部来自 HotspotCard。
    expect(container.querySelectorAll("[data-testid='hotspot-card']").length).toBe(12);
    expect(container.querySelectorAll("[data-plaza-stack] [data-cluster-id]").length).toBe(5);
  });

  it("四个没有数据的槽逐槽隐藏，NEVER 拿手边的字段去顶", () => {
    render(<PlazaCards clusters={[cluster(0)]} />);

    // 广场这条端点没有首见日期/地区/陈旧/判定——一个都不许出现。
    for (const id of ["hotspot-first-seen", "hotspot-region", "hotspot-stale",
                      "hotspot-verdict"]) {
      expect(screen.queryAllByTestId(id)).toHaveLength(0);
    }
    // 有数据的两槽必须在。
    expect(screen.queryAllByTestId("hotspot-heat").length).toBeGreaterThan(0);
  });

  it("category_id 不上产品面，但留在 data-* 上供取证（FB-10 A 类）", () => {
    const { container } = render(<PlazaCards clusters={[cluster(0)]} />);

    expect(container.querySelector("[data-cluster-category='cat-ai']")).not.toBeNull();
    expect(container.textContent).not.toContain("cat-ai");
  });

  it("方向键能切换当前卡——NEVER 只能拖拽", () => {
    const { container } = render(<PlazaCards clusters={CLUSTERS} />);
    const deck = screen.getByTestId("plaza-stack-deck");
    const activeId = (): string | null =>
      container.querySelector("[data-stack-active='true']")!.getAttribute("data-cluster-id");

    expect(activeId()).toBe("c0");
    fireEvent.keyDown(deck, { key: "ArrowRight" });
    expect(activeId()).toBe("c1");
    fireEvent.keyDown(deck, { key: "ArrowLeft" });
    expect(activeId()).toBe("c0");
    // 首张往左要回到末张（精选 5 张），NEVER 卡住不动。
    fireEvent.keyDown(deck, { key: "ArrowLeft" });
    expect(activeId()).toBe("c4");
  });

  it("圆点导航能直接跳，且当前项形状不同（不是同一个点换颜色）", () => {
    const { container } = render(<PlazaCards clusters={CLUSTERS} />);

    const dots = [...container.querySelectorAll(".plaza-stack__dot")];
    expect(dots).toHaveLength(5);
    fireEvent.click(dots[3]);
    expect(container.querySelector("[data-stack-active='true']")!
      .getAttribute("data-cluster-id")).toBe("c3");
    expect(container.querySelector("[data-dot-active='true']")!
      .getAttribute("aria-current")).toBe("true");
  });

  it("点侧卡把它送到前面；点当前卡不换", () => {
    const { container } = render(<PlazaCards clusters={CLUSTERS} />);
    const slot = (id: string): Element =>
      container.querySelector(`[data-plaza-stack] [data-cluster-id='${id}']`)!;

    fireEvent.click(slot("c2"));
    expect(slot("c2").getAttribute("data-stack-active")).toBe("true");
    fireEvent.click(slot("c2"));
    expect(slot("c2").getAttribute("data-stack-active")).toBe("true");
  });

  it("点网格里的卡片把 cluster_id 交给调用方", () => {
    const onSelect = vi.fn();
    const { container } = render(
      <PlazaCards clusters={CLUSTERS} onSelectCluster={onSelect} />,
    );

    fireEvent.click(container.querySelector("[data-plaza-list] [data-cluster-id='c3']")!);
    expect(onSelect).toHaveBeenCalledWith("c3");
  });

  it("计数器是 N / M，M 是精选那一段的张数", () => {
    render(<PlazaCards clusters={CLUSTERS} />);

    expect(screen.getByTestId("plaza-stack-counter").textContent).toContain("01 / 05");
  });

  it("搬运器零计算：热度原样，名字原样", () => {
    const card = clusterToCard(cluster(3));

    expect(card.heat).toBe(97);
    expect(card.nameNative).toBe("热点 3");
    expect(card.nameDisplay).toBeUndefined();
  });

  // SLOT-01：首见日期。库里一直有这一列，端点先前查了不回，于是这一槽永远是空的。
  it("首见日期原样搬运，NEVER 重新格式化", () => {
    const card = clusterToCard({ ...cluster(3), first_seen: "2026-07-03" });

    expect(card.firstSeen).toBe("2026-07-03");
  });

  it("端点没给首见日期时**逐槽隐藏**，NEVER 顶一个占位符", () => {
    // 占位符会让「这个簇刚建」与「这一槽没接上」看起来一样——
    // 而后者正是 SLOT-01 在修的那个毛病，顶上去等于把它藏起来。
    render(<PlazaCards clusters={[cluster(0)]} />);

    expect(screen.queryAllByTestId("hotspot-first-seen")).toHaveLength(0);
  });

  it("屏上那一行就是端点给的那一天", () => {
    render(<PlazaCards clusters={[{ ...cluster(0), first_seen: "2026-07-03" }]} />);

    const [slot] = screen.getAllByTestId("hotspot-first-seen");
    expect(slot.getAttribute("datetime")).toBe("2026-07-03");
    expect(slot.textContent).toBe("2026-07-03");
  });
});
