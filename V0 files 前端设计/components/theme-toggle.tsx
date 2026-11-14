// 主题切换：日间 / 夜间 / 跟随系统。next-themes 负责持久化（localStorage.theme）
// 与首帧前注入 class（无闪烁）。本组件不自己读写 localStorage。
//
// 三态而非两态：默认「跟随系统」，用户显式选过之后才固定——
// 这样「我没选过」与「我选了亮色」是两件事，不把默认伪装成用户意图。
"use client"

import { useEffect, useState } from "react"
import { useTheme } from "next-themes"
import { Sun, Moon, Monitor } from "lucide-react"

const OPTIONS = [
  { value: "light", label: "日间", Icon: Sun },
  { value: "dark", label: "夜间", Icon: Moon },
  { value: "system", label: "跟随系统", Icon: Monitor },
] as const

export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  // 服务端渲染时拿不到用户偏好；未挂载前不渲染选中态，避免 hydration 不一致。
  useEffect(() => setMounted(true), [])

  return (
    <div
      className="inline-flex items-center gap-0.5 border border-rule bg-surface p-0.5"
      style={{ borderRadius: "var(--radius)" }}
      role="group"
      aria-label="主题"
    >
      {OPTIONS.map(({ value, label, Icon }) => {
        const active = mounted && theme === value
        return (
          <button
            key={value}
            type="button"
            onClick={() => setTheme(value)}
            aria-pressed={active}
            title={label}
            className={`inline-flex h-7 w-7 items-center justify-center transition-colors ${
              active ? "bg-raised text-ink" : "text-ink-3 hover:text-ink-2"
            }`}
            style={{ borderRadius: "calc(var(--radius) - 1px)" }}
          >
            <Icon className="h-3.5 w-3.5" strokeWidth={1.5} aria-hidden />
            <span className="sr-only">{label}</span>
          </button>
        )
      })}
    </div>
  )
}
