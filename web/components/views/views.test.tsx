import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { WorkbenchView } from "./WorkbenchView";
import { GateView } from "./GateView";
import { t } from "../../lib/i18n";
import {
  fetchPlazaHot,
  fetchEvidenceCards,
  fetchVerdict,
  VerdictNotReady,
  type PlazaCluster,
  type EvidenceCard,
  type Verdict,
} from "../../lib/viewsClient";

// FE-VIEWS 三界面 + 读客户端。全离线（mock fetch，S2-7）。

const CLUSTERS: PlazaCluster[] = [
  { cluster_id: "c1", canonical_name: "热点甲", category_id: "cat-ai", status: "active",
    by_source: { arxiv: 0.9, weibo: 0.5 }, total_heat: 1.4 },
  { cluster_id: "c2", canonical_name: "热点乙", category_id: "cat-ai", status: "active",
    by_source: { gtrends: 0.3 }, total_heat: 0.3 },
];
const CARDS: EvidenceCard[] = [
  { card_id: "card1", cluster_id: "c1", keyword_ids: ["kw1"], flags: ["novelty"],
    top_links: ["http://x"] },
];
const VERDICT: Verdict = {
  verdict: "C_opportunity", all_satisfied: ["A", "B"],
  key_citation_ids: ["cit-1"], rationale_fact_ids: ["fact-1"],
  competitors: [{ name: "Acme", url: "http://a", strength: "weak" }],
  // TYPE-03：这里原先写的是 `true`。后端一直回的是**对象**，
  // 而前端把类型标成了 `boolean`——夹具照着错类型写，于是两边一起错，
  // 谁都看不出来。改类型的那一刻 TypeScript 当场拦下了这一行。
  constraints_checked: {
    order: ["A_infeasible", "B_red_ocean", "C_opportunity", "D_insufficient"],
    demoted_by_alignment: [],
    rule_a: { satisfied: false, used_user_evidence_only: false,
              blocked_pending_optin: false },
    rule_b: { satisfied: false, by_count: false, by_strength: false,
              reachable_count: 0, strong_names: [] },
    rule_c: { satisfied: true, failed_conditions: [], blocking_competitors: [] },
    gap_count: 1,
  },
  gaps: [{ missing_what: "价格", cause: "missing_data", action: "search" }],
};

// PLAZA-01：`PlazaView`（`ul/li` 版广场）已退役并删除，它这两条判据随之移走。
// 广场的判据现在在 `web/components/plaza/plazaCards.test.tsx` 与
// `tests/v041/test_plaza_cards.py`——**同样的两件事（列簇按后端序、空态说空态）
// 在那边逐条对得上，NEVER 借退役之名把判据一并删掉。**

describe("WorkbenchView 工作台", () => {
  it("证据卡只读 + 引用源链接 + 关联假设留白（Q-010）", () => {
    const { container } = render(<WorkbenchView clusterId="c1" cards={CARDS} />);
    expect(container.querySelector("[data-card-id='card1']")).not.toBeNull();
    const link = container.querySelector("[data-link='http://x']");
    expect(link!.getAttribute("href")).toBe("http://x");
    expect(container.querySelector("[data-hypothesis-deferred]")!.textContent).toBe(
      t("workbench.hypothesis_deferred"));
    // 只读：无编辑控件
    expect(container.querySelector("input,textarea,button")).toBeNull();
  });
});

describe("GateView Gate①", () => {
  it("四分类全引用据实；前端 NEVER 自判（verdict 直取后端值）", () => {
    const { container } = render(<GateView verdict={VERDICT} />);
    // verdict 直取后端 C_opportunity，非前端计算
    expect(container.querySelector("[data-verdict='C_opportunity']")).not.toBeNull();
    expect(container.querySelector("[data-citation-id='cit-1']")).not.toBeNull();
    expect(container.querySelector("[data-fact-id='fact-1']")).not.toBeNull();
    expect(container.querySelector("[data-competitor='Acme']")).not.toBeNull();
    expect(container.querySelector("[data-gap-cause='missing_data']")).not.toBeNull();
  });
});

describe("viewsClient", () => {
  it("fetchPlazaHot / fetchEvidenceCards / fetchVerdict", async () => {
    const plazaFetch = vi.fn(async () =>
      new Response(JSON.stringify({ clusters: CLUSTERS }), { status: 200 }));
    expect(await fetchPlazaHot("2026-07-20", { fetchImpl: plazaFetch as unknown as typeof fetch }))
      .toHaveLength(2);
    const cardFetch = vi.fn(async () =>
      new Response(JSON.stringify({ evidence_cards: CARDS }), { status: 200 }));
    expect(await fetchEvidenceCards("c1", { fetchImpl: cardFetch as unknown as typeof fetch }))
      .toHaveLength(1);
    const vFetch = vi.fn(async () =>
      new Response(JSON.stringify({ verdict: VERDICT }), { status: 200 }));
    expect((await fetchVerdict("j1", { fetchImpl: vFetch as unknown as typeof fetch })).verdict)
      .toBe("C_opportunity");
  });
  it("fetchVerdict 404 → VerdictNotReady", async () => {
    const f = vi.fn(async () => new Response("{}", { status: 404 }));
    await expect(fetchVerdict("nope", { fetchImpl: f as unknown as typeof fetch }))
      .rejects.toBeInstanceOf(VerdictNotReady);
  });
});
