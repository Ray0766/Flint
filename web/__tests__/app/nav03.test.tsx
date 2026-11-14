/**
 * NAV-03：「入台」按成功之后要把人带过去。
 *
 * ## 改前的实况
 *
 * 三个动作按钮**真的在调后端**（`cardActions` 的三条），而按完停在原地——
 * 用户不知道有没有成事。`DEC-042` ② 裁决：**「入台」才是进图谱工作台的那条路**。
 *
 * ## 这一组判据守的四件事
 *
 * 1. **成功才导航**，且去哪一个由服务端说（`graph_id`）。
 * 2. **失败 NEVER 导航**：留在原地，并显示服务端自己的说明——
 *    NEVER 用一句「操作失败」盖住后端说的话。
 * 3. **收藏与分享不导航**：它们是动作不是去处。把人带走的话，
 *    他刚点的那张卡就没了，而他多半还想接着看别的。
 * 4. **「按完没反应」与「按完失败」NEVER 长得一样**：三条路各有各的回执。
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PlazaCards } from "../../components/plaza/PlazaCards";
import { workbenchTarget } from "../../components/plaza/cardActions";
import { t } from "../../lib/i18n/t";
import type { PlazaCluster } from "../../lib/viewsClient";

const CLUSTER: PlazaCluster = {
  cluster_id: "c-1", canonical_name: "固态电池", category_id: "energy",
  status: "active", by_source: { weibo: 100 }, total_heat: 100,
};

function reply(status: number, body: unknown) {
  return Promise.resolve({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response);
}

let went: string[] = [];

beforeEach(() => {
  went = [];
  Object.defineProperty(window, "location", {
    configurable: true,
    value: { ...window.location, assign: (u: string) => went.push(u) },
  });
});

const press = async (which: string) => {
  await act(async () => { fireEvent.click(screen.getByTestId(`action-${which}`)); });
};

describe("入台之后", () => {
  it("成功就把人带到那个工作台，去哪一个**由服务端说**", async () => {
    vi.stubGlobal("fetch", vi.fn(() => reply(201, { graph_id: "wb-77" })));
    render(<PlazaCards clusters={[CLUSTER]} />);

    await press("workbench");

    await waitFor(() => expect(went).toEqual(["/workbenches/wb-77"]));
  });

  it("**失败 NEVER 导航**，且屏上是服务端自己的说明（阴性对照）", async () => {
    vi.stubGlobal("fetch", vi.fn(() =>
      reply(500, { message: "图谱库连不上" })));
    render(<PlazaCards clusters={[CLUSTER]} />);

    await press("workbench");

    await waitFor(() => {
      expect(screen.getByTestId("action-outcome").textContent).toBe("图谱库连不上");
    });
    expect(went).toEqual([]);          // 没跳走
  });

  it("「还没接」也不导航——那是三种「不成」里的另一种", async () => {
    // 今天的真实答复：POST /workbenches 回框架的 404（没有 code）。
    vi.stubGlobal("fetch", vi.fn(() => reply(404, { detail: "Not Found" })));
    render(<PlazaCards clusters={[CLUSTER]} />);

    await press("workbench");

    await waitFor(() => {
      expect(screen.getByTestId("action-outcome").getAttribute("data-outcome-kind"))
        .toBe("not_provided");
    });
    expect(went).toEqual([]);
  });

  it("成了、却没说是哪一个——**留在原地并说清楚**，NEVER 拼一个 id 跳过去", async () => {
    vi.stubGlobal("fetch", vi.fn(() => reply(201, { ok: true })));
    render(<PlazaCards clusters={[CLUSTER]} />);

    await press("workbench");

    await waitFor(() => {
      expect(screen.getByTestId("action-note").textContent)
        .toBe(t("card.action.workbench_no_target"));
    });
    expect(went).toEqual([]);
    // 「成了」这句照说：用户的东西确实存下了，与「失败」是两件事。
    expect(screen.getByTestId("action-outcome").getAttribute("data-outcome-kind"))
      .toBe("ok");
  });

  it("`graph_id` 只认这一个名字——认两个别名的话，服务端改口时会安静地跳错地方", () => {
    expect(workbenchTarget({ kind: "ok", detail: { graph_id: "wb-1" } })).toBe("wb-1");
    expect(workbenchTarget({ kind: "ok", detail: { workbench_id: "wb-1" } })).toBeNull();
    expect(workbenchTarget({ kind: "ok", detail: { graph_id: "" } })).toBeNull();
    expect(workbenchTarget({ kind: "not_provided", reason: "没挂" })).toBeNull();
  });
});

describe("收藏与分享", () => {
  it("**不导航**：它们是动作不是去处", async () => {
    vi.stubGlobal("fetch", vi.fn(() => reply(201, { graph_id: "wb-77" })));
    render(<PlazaCards clusters={[CLUSTER]} />);

    await press("favorite");
    await waitFor(() => expect(screen.queryByTestId("action-outcome")).not.toBeNull());
    expect(went).toEqual([]);

    await press("share");
    expect(went).toEqual([]);
  });

  it("成功回执明确——**按完没反应与按完失败 NEVER 长得一样**", async () => {
    vi.stubGlobal("fetch", vi.fn(() => reply(201, { favorite_id: "fav-1" })));
    const { container } = render(<PlazaCards clusters={[CLUSTER]} />);

    // 按之前：一个字都没有（`null` = 还没点过，**不是**「点了没反应」）。
    expect(container.querySelector("[data-testid='action-outcome']")).toBeNull();

    await press("favorite");

    await waitFor(() => {
      const line = screen.getByTestId("action-outcome");
      expect(line.getAttribute("data-outcome-kind")).toBe("ok");
      expect(line.getAttribute("data-outcome-of")).toBe("favorite");
      expect(line.textContent).toBe(t("card.action.done"));
    });
  });

  it("失败时说的是服务端那句话，NEVER 一句「操作失败」盖住它", async () => {
    vi.stubGlobal("fetch", vi.fn(() =>
      reply(422, { detail: { allowed: ["deliverable", "graph", "topic"] } })));
    render(<PlazaCards clusters={[CLUSTER]} />);

    await press("share");

    await waitFor(() => {
      const line = screen.getByTestId("action-outcome");
      expect(line.getAttribute("data-outcome-kind")).toBe("unsupported");
      // 清单**来自服务端**，前端不自带一份（那份会与冻结件各自漂移）。
      expect(line.textContent).toContain("deliverable");
    });
    expect(went).toEqual([]);
  });
});
