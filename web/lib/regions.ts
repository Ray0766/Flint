// REGION-11 / DEC-040：未归区——`global` 与 `NULL` 在筛选面上的去处。
//
// ## 它不是第十个地区，是第十个**选项**
//
// 库里 `clusters.region` 的分布（steward 实查）：`global = 103` · `CN = 89` · `NULL = 1`。
// `global` 是 `ghtrend` 写死的常量，**不是地理事实**。两条错法各自的样子：
//
// - 把它当第九区 → 用户在**地理列表**里选到一个不存在的地方；
// - 让它从筛选面消失 → 那 104 条只在「不筛」时出现，**一旦开始筛就蒸发**。
//
// 「未归区」是唯一诚实的说法：它承认这些簇存在、也承认我们不知道它们的产地。
//
// ## 记号只有一处定义
//
// 后端那一处是 `flint/api/views.py#UNASSIGNED_REGION`，两边逐字相同，
// `tests/v041/test_unassigned_region.py` 判它们相等。
// 各写一份的话，改名那天只有一处会跟上——而**症状是「选了未归区什么都没有」**，
// 看起来像后端坏了。
//
// ## 为什么不塞进 `options.region`
//
// 那是 locale 的**地理词表**（冻结件 `contracts_v04.Region`，`DEC-056` 之后十项），
// `PUT /settings/locale` 拿它校验用户偏好。塞进去等于允许把「未归区」
// 存成一个人的常住地。所以清单仍然只有一处真相（`LOC-01`），
// 未归区由**筛选面**在取到那份清单之后追加。

import { t } from "./i18n/t";

/** 筛选面上的未归区。与后端 `flint/api/views.py#UNASSIGNED_REGION` 逐字相同。 */
export const UNASSIGNED_REGION = "unassigned";

/**
 * 把地区清单补上未归区，得到**筛选面**的完整选项。
 *
 * 拿不到那份清单时返回 `null` 原样传下去——**NEVER 只返回未归区一项**：
 * 一份只剩第十项的清单读起来像「只有这一个区可选」，那是一句结论；
 * 真相是「这份清单没查到」，而 `RegionSwitch` 自己会如实标未提供态。
 */
export function withUnassigned(
  regions: readonly string[] | null | undefined,
): readonly string[] | null {
  if (!regions || regions.length === 0) return null;
  return regions.includes(UNASSIGNED_REGION)
    ? regions
    : [...regions, UNASSIGNED_REGION];
}

/**
 * 选项在屏上的文案。
 *
 * 地区码**原样显示**（`CN` 就是 `CN`，映射成中文名是另一件事）；
 * 未归区走文案——`unassigned` 是内部记号，印在屏上就是 `FB-10` 点名的
 * **A 类脚手架：开发要看的东西跑到了产品面**。
 */
export function regionOptionLabel(region: string): string {
  return region === UNASSIGNED_REGION ? t("region.unassigned.label") : region;
}

/** CN-02 / `DEC-045`：本版广场默认落在哪个区。
 *  后端那一份真相在 `flint/region/version_scope.py#DEFAULT_REGION`；
 *  这里是**首屏还没取到数时**用的初值——两处都写死 CN 而不是让前端去猜，
 *  因为首屏那一瞬间还没有任何服务端答复可读。
 *  下一版解除收窄时两处一起改（`CURRENT_SCOPE` 是那时的检索起点）。 */
export const DEFAULT_REGION = "CN";
