// DESIGN-27（隔离带·G2）：样板可辨识三件套（占位语法 + 水印 + `-mock` 后缀）。
//
// ## 这不是 UI 瑕疵，是品牌级事故的防线
//
// 探索期样板里的示例数字（「渗透率 42.7%」）一旦被截图外传当成真报告，
// 燧石「每个数字有出处」这条立身之本就当场破产——而外传的人往往不知道
// 自己拿的是样板。三件套的作用是：**无论从哪个出口流出去，它都自带「这是样板」这句话**。
//
// - **占位语法**：示例数字必须写成 `XX.X%`、来源必须写成 `[来源待补]` 或 `SRC-XXXX`。
//   一个具体的数字（42.7%）看起来就是真的，而 `XX.X%` 一眼假。
// - **水印**：页面上有一层「样板」标记，且**不可移除**——不可移除的可执行化
//   就是：渲染与导出在看不到水印节点时**拒绝**，而不是补一个回去。
//   补回去的话，改水印的人会以为自己成功了，然后在别处继续改。
// - **`-mock` 后缀**：文件名自带标记。截图外传拦不住，但发文件时它就在标题栏上。
//
// ## 为什么拒绝而不是修复
//
// 「检测到缺失就补一个」听起来更友好，但那等于告诉调用方「你怎么改都行，我兜着」。
// 而这条规则的全部意义是**它兜不住**：缺水印 = 这份产物没资格出去。

export const MOCK_WATERMARK_ATTR = "data-mock-watermark";
export const MOCK_FILENAME_SUFFIX = "-mock";

// 四条模式放在 mock-syntax.json：它们是**检测模式**不是界面文案，中文要逐字保留
// （key 化会让它们不再匹配任何东西）——与 synthesis-blacklist.json 同一条口径。
import syntax from "./mock-syntax.json";

const PLACEHOLDER_NUMBER = new RegExp(syntax.placeholderNumber);
const PLACEHOLDER_SOURCE = new RegExp(syntax.placeholderSource);
const CONCRETE_NUMBER = new RegExp(syntax.concreteNumber, "g");
const CONCRETE_SOURCE = new RegExp(syntax.concreteSource, "g");

export type MockViolation = {
  kind: "concrete_number" | "concrete_source" | "missing_watermark" | "filename";
  detail: string;
};

/** 样板正文里的占位语法检查。 */
export function checkMockPlaceholders(html: string): MockViolation[] {
  const violations: MockViolation[] = [];

  // 先摘出具体来源，再在**剩下的文字**里找具体数字：不这么做的话，
  // `SRC-1234` 会同时命中「具体来源」与「具体数字」两条——同一个问题报两遍，
  // 用户改完一处发现清单还剩一条，会以为自己没改对。
  const withoutSources = html.replace(CONCRETE_SOURCE, (hit) => {
    violations.push({ kind: "concrete_source", detail: hit });
    return " ".repeat(hit.length);
  });
  for (const m of withoutSources.matchAll(CONCRETE_NUMBER)) {
    violations.push({ kind: "concrete_number", detail: m[0] });
  }
  return violations;
}

export function hasWatermark(html: string): boolean {
  return html.includes(MOCK_WATERMARK_ATTR);
}

export function isMockFilename(name: string): boolean {
  const base = name.replace(/\.[^.]+$/, "");
  return base.endsWith(MOCK_FILENAME_SUFFIX);
}

export class MockIdentityViolation extends Error {
  constructor(public readonly violations: MockViolation[]) {
    super(
      "mock identity violated: " +
        violations.map((v) => `${v.kind}(${v.detail})`).join("; "),
    );
  }
}

// 样板的渲染/导出闸门：三件套缺一即拒。
// （行注释而非 JSDoc：扫描器对跨行块注释的已知假阳性，见 DEC-013 / 卡 I18N-09。）
export function guardMock(
  html: string,
  filename: string,
): { html: string; filename: string } {
  const violations = checkMockPlaceholders(html);
  if (!hasWatermark(html)) {
    // NEVER 补一个水印回去：补回去的话，改水印的人会以为自己成功了
    violations.push({ kind: "missing_watermark", detail: MOCK_WATERMARK_ATTR });
  }
  if (!isMockFilename(filename)) {
    violations.push({ kind: "filename", detail: filename });
  }
  if (violations.length > 0) throw new MockIdentityViolation(violations);
  return { html, filename };
}

/** 占位语法是否被正确使用（供样板作者自查，与闸门共用同一套正则）。 */
export function usesPlaceholderSyntax(text: string): boolean {
  return PLACEHOLDER_NUMBER.test(text) || PLACEHOLDER_SOURCE.test(text);
}
