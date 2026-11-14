// DESIGN-03：设计台三接口抽象（G11）。
//
// **Html\* 是唯一实现**：渲染、按区间打补丁、导出，三件事各自一个接口。
// 三者都**不改字节**（除了补丁那段区间）——承 DESIGN-02 的零构建口径：
// 预览、打补丁、导出走的是同一份字节，中间任何一次「顺手格式化」都会让
// 用户手改过的地方悄悄变形。
//
// **Jsx\* 存在但抛未实现**：接口位置先定下来，将来接 JSX 产物时改的是实现
// 而不是调用点。抛错让「它现在没有」在运行时是**响亮的**——一个返回空字符串的
// 假实现会让上层以为渲染成功了，然后把一片空白当成产物导出去。
// 这与 SCHEMA-11 的 friend 缝同一条纪律：NEVER 用 flag 或空返回占位。

export class NotImplementedError extends Error {}

/** 按字节区间的一次替换。区间是 [start, end)。 */
export type PatchSpan = {
  start: number;
  end: number;
  text: string;
};

export interface DesignRenderer {
  render(source: string): string;
}

export interface DesignPatcher {
  patch(source: string, span: PatchSpan): string;
}

export interface DesignExporter {
  export(source: string): string;
}

function assertSpan(source: string, span: PatchSpan): void {
  const valid =
    Number.isInteger(span.start) &&
    Number.isInteger(span.end) &&
    span.start >= 0 &&
    span.end >= span.start &&
    span.end <= source.length;
  if (!valid) {
    // 越界或倒置 = 调用方算错了。猜他想改哪一段，会把补丁打在别的地方，
    // 而那种错在导出之前谁都看不出来。
    throw new RangeError(
      `patch span out of range: [${span.start}, ${span.end}) of ${source.length}`,
    );
  }
}

export class HtmlRenderer implements DesignRenderer {
  render(source: string): string {
    return source;                       // 零改写：预览里那段字节就是最终那段字节
  }
}

export class HtmlPatcher implements DesignPatcher {
  patch(source: string, span: PatchSpan): string {
    assertSpan(source, span);
    return source.slice(0, span.start) + span.text + source.slice(span.end);
  }
}

export class HtmlExporter implements DesignExporter {
  export(source: string): string {
    return source;                       // 导出不是二次渲染
  }
}

const JSX_MESSAGE = "jsx pipeline: post-v1";

export class JsxRenderer implements DesignRenderer {
  render(source: string): string {
    void source;
    throw new NotImplementedError(JSX_MESSAGE);
  }
}

export class JsxPatcher implements DesignPatcher {
  patch(source: string, span: PatchSpan): string {
    void source;
    void span;
    throw new NotImplementedError(JSX_MESSAGE);
  }
}

export class JsxExporter implements DesignExporter {
  export(source: string): string {
    void source;
    throw new NotImplementedError(JSX_MESSAGE);
  }
}
