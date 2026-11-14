// DESIGN-08：Tweaks 参数面板的两条路径（G13）。
//
// ## 快路径：拖动只 patch CSS 变量
//
// 重建 srcdoc 等于整页重新加载——滚动位置回到顶部、动画从头播、iframe 里的输入框失焦。
// 用户拖着滑块调间距，每动一格页面就跳一次，那个面板根本没法用。
// 所以拖动期只调 `style.setProperty(--x, value)`，**一次都不重建**。
//
// 只认 CSS 变量：改 `padding` 这类普通属性要动结构，不属于「改一个值」的快路径；
// 让它悄悄走快路径会让用户以为改成了，而下次重建时那处改动并不存在。
//
// ## 落盘路径：按字节区间回写
//
// 整段重写会把用户手改过的地方一起冲掉，也会让 diff 变成「整文件变了」——
// 之后没有人能一眼看出这次到底动了什么。所以只替换**值**所占的那一段字节，
// 缩进、分号、周围的空白一个字节不动。
//
// 变量不存在时报错，NEVER 悄悄追加一条定义：追加会让源码里多出一条用户从没写过的规则，
// 而他以为自己只是拖了个滑块。

export type Tweak = {
  /** CSS 变量名，必须以 -- 开头 */
  name: string;
  value: string;
};

export type FastPathTarget = {
  /** 预览文档根元素的 style（快路径就作用在它上面） */
  style: CSSStyleDeclaration;
  /** 慢路径：重建整份预览。快路径下**一次都不该被调**。 */
  rebuildSrcdoc: () => void;
};

export type ByteSpan = { start: number; end: number };

export function applyTweak(tweak: Tweak, target: FastPathTarget): void {
  if (!tweak.name.startsWith("--")) {
    throw new Error(
      `fast path takes CSS variables only, got ${tweak.name}: ` +
        "changing a plain property needs a structural edit, not a value tweak",
    );
  }
  if (tweak.value.trim() === "") {
    // 空串会把那条样式整个抹掉，而用户只是把滑块拖到了最左端
    throw new Error(`empty value for ${tweak.name}: that would delete the rule`);
  }
  target.style.setProperty(tweak.name, tweak.value);
}

// 定义形态：`--name: <值>;` 或 `--name: <值>}`。引用形态 `var(--name)` 不匹配——
// 引用的位置回写过去，改的是别人用它的地方，而不是它自己。
function definitionPattern(name: string): RegExp {
  const escaped = name.replace(/[.*+?^${}()|[\]\\-]/g, "\\$&");
  return new RegExp(`${escaped}\\s*:\\s*([^;}]+)`);
}

/** 变量**值**所占的字节区间；找不到定义返回 null。 */
export function findVariableSpan(source: string, name: string): ByteSpan | null {
  const match = definitionPattern(name).exec(source);
  if (match === null || match.index === undefined) return null;
  const value = match[1];
  const trimmedStart = match.index + match[0].length - value.length;
  const leading = value.length - value.trimStart().length;
  const start = trimmedStart + leading;
  return { start, end: start + value.trim().length };
}

/** 按字节区间回写一个变量的值。其余字节逐字不动。 */
export function patchSource(source: string, name: string, value: string): string {
  const span = findVariableSpan(source, name);
  if (span === null) {
    throw new Error(
      `no definition of ${name} in source: refusing to append one — ` +
        "the user dragged a slider, they did not ask for a new rule",
    );
  }
  return source.slice(0, span.start) + value + source.slice(span.end);
}
