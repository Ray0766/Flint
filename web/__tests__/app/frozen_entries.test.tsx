/**
 * NARROW-05: the `DEC-066` freeze list closes its entries in the web app.
 *
 * Freezing closes the way in and deletes nothing, so each case checks both
 * halves: the entry is gone from what renders, and the thing behind it is
 * still there (the nav table still lists the route, the button component
 * still renders its buttons when a caller asks for them).
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShell, NAV_ITEMS } from "../../components/shell/AppShell";
import { HotspotCardActions } from "../../components/hotspot-card-actions/HotspotCardActions";
import { FROZEN, isFrozenNavHref } from "../../lib/frozen";

vi.mock("next/navigation", () => ({ usePathname: () => "/plaza" }));

const FROZEN_HREFS = ["/workbench", "/favorites", "/design", "/settings/locale"];

describe("frozen entries in the shell", () => {
  it("the nav renders no link into a frozen item", () => {
    const { container } = render(<AppShell><p>x</p></AppShell>);
    const hrefs = [...container.querySelectorAll("header a[href]")].map((a) =>
      a.getAttribute("href"),
    );

    for (const href of FROZEN_HREFS) expect(hrefs).not.toContain(href);
    // control: the chain's own entries are still there
    expect(hrefs).toContain("/plaza");
    expect(hrefs).toContain("/account");
  });

  it("the routes are still in the nav table, only switched off", () => {
    const listed = NAV_ITEMS.map((i) => i.href);
    for (const href of FROZEN_HREFS) {
      expect(listed).toContain(href);
      expect(isFrozenNavHref(href)).toBe(true);
    }
    expect(isFrozenNavHref("/plaza")).toBe(false);
  });

  it("the region and language dropdowns are not in the shell", () => {
    const { container } = render(<AppShell><p>x</p></AppShell>);
    expect(container.querySelector(".app-shell__locale")).toBeNull();
    expect(container.querySelector("[data-testid='shell-lang']")).toBeNull();
    // control: the theme switch is not frozen and stays in the bar
    expect(container.querySelector(".app-shell__theme")).not.toBeNull();
  });
});

describe("frozen entries on the plaza card", () => {
  const noop = (): void => {};

  it("favorite, add-to-workbench and share are not rendered", () => {
    render(<HotspotCardActions onFavorite={noop} onAddToWorkbench={noop} onShare={noop} />);
    expect(screen.queryByTestId("action-favorite")).toBeNull();
    expect(screen.queryByTestId("action-workbench")).toBeNull();
    expect(screen.queryByTestId("action-share")).toBeNull();
  });

  it("every switch it reads is on, so the closing is the table's doing", () => {
    expect(FROZEN.favorites && FROZEN.graphWorkbench && FROZEN.share).toBe(true);
  });
});
