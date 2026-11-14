import React from "react"
import type { Metadata } from 'next'
import { Fraunces, Inter, IBM_Plex_Mono } from 'next/font/google'
import localFont from 'next/font/local'
import { Analytics } from '@vercel/analytics/next'
import { ThemeProvider } from '@/components/theme-provider'
import './globals.css'

// 西文 display：有性格的高对比衬线
const fraunces = Fraunces({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-fraunces',
})

// 西文正文
const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
})

// 数据 / 出处：等宽 tabular
const plexMono = IBM_Plex_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  display: 'swap',
  variable: '--font-plex-mono',
})

// 中文 display 宋体：自托管子集（public/fonts/，仅含全站实际用到的汉字），
// 500 / 600 两字重。用 next/font/local 装载，构建期不访问外网。
// 用途限页面级标题与 verdict 判定词——用字量小，子集体积可控。
const notoSerifSC = localFont({
  src: [
    { path: '../public/fonts/noto-serif-sc-500.woff2', weight: '500', style: 'normal' },
    { path: '../public/fonts/noto-serif-sc-600.woff2', weight: '600', style: 'normal' },
  ],
  display: 'swap',
  variable: '--font-noto-serif-sc',
})

export const metadata: Metadata = {
  title: 'Flint · 带出处的卷宗',
  description: '燧石：一份带出处的分析卷宗。视觉不编码后端未给出的确定度。',
  generator: 'v0.app',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    // suppressHydrationWarning：next-themes 在首帧前用内联脚本改 <html> 的 class，
    // 服务端渲染时那个 class 还不存在，属预期差异（仅此一处，不掩盖真实 hydration 问题）。
    <html lang="zh-CN" suppressHydrationWarning>
      <body
        className={`${fraunces.variable} ${inter.variable} ${plexMono.variable} ${notoSerifSC.variable} font-sans antialiased`}
      >
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          {children}
        </ThemeProvider>
        <Analytics />
      </body>
    </html>
  )
}
