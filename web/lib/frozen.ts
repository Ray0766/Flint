/**
 * `DEC-066` freeze list, as the web app applies it (`NARROW-05`).
 *
 * Freezing means "no more investment, close the way in". It does not delete
 * anything: every frozen screen is still in `app/`, its route still answers
 * when typed into the address bar, and its component and tests are untouched.
 * What goes is the **entry**: the nav item, the button, the dropdown.
 *
 * Every frozen entry reads its switch from this one table, so unfreezing an
 * item is one edit here (and the only way to unfreeze is a new owner ruling,
 * `CLAUDE.md` S1). Which screen belongs to which item I checked by reading
 * the screen, not its name:
 *
 * - `/workbench` offers the five human templates and nothing else
 *   (`TEMPLATE_IDS` = generic / startup / engineering / grant / thesis); the
 *   vibe_pack route goes through `/projects/[id]/proposal`, which stays open;
 * - the plaza card's "add to workbench" button lands on the graph workbench
 *   (`/workbenches/{id}`, `DEC-042`);
 * - `/account` itself is an identity screen and is not on the freeze list, so
 *   it stays; only its link to `/billing` closes.
 */
export const FROZEN = {
  /** 收藏: `/favorites` in the nav, the plaza card's favorite button. */
  favorites: true,
  /** 分享: the plaza card's share button. */
  share: true,
  /** 图谱工作台: the plaza card's "add to workbench" button. */
  graphWorkbench: true,
  /** 设计工作台: `/design` in the nav. */
  designWorkbench: true,
  /** 五套人类模板: `/workbench` in the nav. */
  humanTemplates: true,
  /** 九个地区与英文界面: `/settings/locale` in the nav, the region and language
   *  dropdowns in the shell, the plaza's region switch. */
  regionsAndLanguages: true,
  /** 支付与计费: the account screen's link to `/billing`. */
  billing: true,
} as const satisfies Record<string, boolean>;

/** Nav entries that lead into a frozen item, keyed to the switch that closes them. */
const NAV_FREEZE: Readonly<Record<string, keyof typeof FROZEN>> = {
  "/workbench": "humanTemplates",
  "/favorites": "favorites",
  "/design": "designWorkbench",
  "/settings/locale": "regionsAndLanguages",
};

/** True when this nav href leads into a frozen item. */
export function isFrozenNavHref(href: string): boolean {
  const item = NAV_FREEZE[href];
  return item !== undefined && FROZEN[item];
}
