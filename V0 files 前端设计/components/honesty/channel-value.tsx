// 状态：TableCell(FactCell.fact_id / PriceCell.price_entry_id+quantity) · ProfileRef.field_path → 三通道分派
//
// **层级原则（2026-08-01 修）**：契约里这三支只带**标识符**，不带可读数值
// （FactCell 只有 fact_id，没有 value）。所以标识符 MUST 是**从属层级**——
// 之前把 fact_id 按 31px 主值渲染，导致 390px 窄屏上 `fact-demo-vecdb-cost`
// 占掉四行大字、把同行的人读内容（行名）挤成一字一行。引用标识符比内容本身还响 = 主次颠倒。
// 现在：标识符 12px 等宽可断行，通道字形印记不变（非颜色载体）。
//
// ⚠️ **留给未来的缝（owner 裁决 ②，NEVER 照抄现样式）**：
// 当解引用端点（GET /facts/{id} 一类）建成、这三支能拿到**真数值**之后，
// 版式 MUST 反过来分两层：**数值走大字号（那才是读者要看的东西），id 继续保持小字从属**。
// 现在三处统一 12px 是「只有 id 可显」时的正确解，**不是**「数字就该小」的结论。
// 接解引用的人若直接沿用本文件现样式，会把最该突出的数字压小——那是回归，不是一致。
import type { FactCell, PriceCell, ProfileRef } from "@/lib/types"

// 三通道数据印记：F / ¥ / P 同为墨色，靠**字形**与边框区分，NEVER 靠颜色。
function DataMark({ glyph }: { glyph: string }) {
  return (
    <span
      className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-[1px] border border-ink-3 font-mono text-[10px] font-medium text-ink-2"
      aria-hidden
    >
      {glyph}
    </span>
  )
}

// 标识符行：印记 + 可断行的等宽 id。min-w-0 + break-all 是窄屏不溢出的关键。
function IdRow({ glyph, id }: { glyph: string; id: string }) {
  return (
    <span className="flex min-w-0 items-start gap-1.5">
      <span className="mt-[1px]">
        <DataMark glyph={glyph} />
      </span>
      <span className="tabular min-w-0 break-all font-mono text-[12px] leading-[1.5] text-ink">
        {id}
      </span>
    </span>
  )
}

// fact 通道：FactCell.fact_id。只有标识符，无数值 → 标识符按从属层级呈现。
export function FactValue({ fact_id, display }: Pick<FactCell, "fact_id"> & { display: string }) {
  return (
    <span className="flex min-w-0 flex-col gap-1">
      <IdRow glyph="F" id={display} />
      <span className="break-all font-mono text-[10px] leading-[1.5] text-ink-3">
        fact_id · {fact_id}
      </span>
    </span>
  )
}

// price 通道：PriceCell.price_entry_id + quantity。quantity **原样呈现，NEVER 乘算**。
export function PriceValue({
  price_entry_id,
  quantity,
  display,
}: Pick<PriceCell, "price_entry_id" | "quantity"> & { display: string }) {
  return (
    <span className="flex min-w-0 flex-col gap-1">
      <IdRow glyph="¥" id={display} />
      <span className="tabular font-mono text-[12px] leading-[1.5] text-ink-2">× {quantity}</span>
      <span className="break-all font-mono text-[10px] leading-[1.5] text-ink-3">
        price_entry_id · {price_entry_id} · qty {quantity}
      </span>
    </span>
  )
}

// profile 通道：ProfileRef.field_path。档案引用。
export function ProfileValue({ field_path }: Pick<ProfileRef, "field_path">) {
  const leaf = field_path.split(".").slice(-1)[0]
  return (
    <span className="inline-flex min-w-0 flex-col gap-1 align-middle">
      <IdRow glyph="P" id={leaf} />
      <span className="break-all font-mono text-[10px] leading-[1.5] text-ink-3">
        field_path · {field_path}
      </span>
    </span>
  )
}

// 统一入口：按通道分派。三通道互不混用。
export function ChannelValue(
  props:
    | ({ channel: "fact" } & Pick<FactCell, "fact_id"> & { display: string })
    | ({ channel: "price" } & Pick<PriceCell, "price_entry_id" | "quantity"> & { display: string })
    | ({ channel: "profile" } & Pick<ProfileRef, "field_path">),
) {
  switch (props.channel) {
    case "fact":
      return <FactValue fact_id={props.fact_id} display={props.display} />
    case "price":
      return (
        <PriceValue
          price_entry_id={props.price_entry_id}
          quantity={props.quantity}
          display={props.display}
        />
      )
    case "profile":
      return <ProfileValue field_path={props.field_path} />
  }
}
