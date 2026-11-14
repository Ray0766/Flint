# NEXOVA Design System

NEXOVA is a web-hosting company (domains, VPS/cloud/managed servers, bare metal, email). This design system was built from a written spec for its 404 error page — a single viewport-height layout over a cinematic Earth-from-space video loop. No Figma, codebase, or other source was provided; everything here derives from that spec.

**Sources:** written 404-page spec (React + Tailwind + Lucide); background video `https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260613_180732_a54afbf6-b30d-470e-861f-669871f09f67.mp4`; font stylesheet `https://db.onlinewebfonts.com/c/e66905e07608167a84e6ad52f638c3c6?family=Helvetica+Now+Var`.

## CONTENT FUNDAMENTALS

- Voice is casual and lightly playful in body copy: "This page seems to have slipped beyond our reach :/" — a text emoticon, not emoji. Second person implied, never corporate apology-speak.
- Labels, CTAs, and column titles are TERSE ALL-CAPS: "LOG IN", "SEND IT", "HELP US", "JOIN FOR EXCLUSIVE DEALS", "CONNECT". Two–four words max.
- Nav links are single capitalized words: Domain, Servers, Cloud, Managed, Email, Privacy.
- Footer links are short Title Case verb/noun pairs: "Find Domain", "Move Domains", "Open a Ticket", "We Hire".
- No emoji anywhere; the only expressive character is the `:/` emoticon.
- Vibe: cosmic, calm, confident — vast imagery with minimal, quiet copy.

## VISUAL FOUNDATIONS

- **Color:** near-monochrome white-on-dark. The page surface is the video itself (deep blue space; fallback `--nx-space-900 #050d1a`). Text is white at three alpha tiers: 100% (headings, titles), 80% (body/nav), 50% (footer links, social icons). The single chromatic accent is the emerald→cyan gradient `--nx-grad-cta` (#34d399 → #06b6d4), used only on primary CTAs (LOG IN, SEND IT). No other hues.
- **Type:** one family — Helvetica Now Var (fallback Helvetica/Arial), loaded from an external stylesheet (see `tokens/fonts.css`; no local binaries). Extreme weight contrast: 300 light for hero lines, 900 black for the giant 404, 700 bold for tiny tracked-out caps labels (0.15–0.2em), 600 semibold buttons. Display type is tracked tight (−0.05em); labels tracked wide.
- **Backgrounds:** full-bleed autoplaying muted looping video, `object-fit:cover`, behind a `z-10` content column. No patterns, illustrations, or gradients as backgrounds (gradient is buttons-only).
- **Transparency & blur:** the signature effect. Liquid-glass CTAs (1% white fill, blur(4px), inset top highlight, masked 1.4px gradient hairline border — `.liquid-glass`); mobile menu is a pure backdrop-blur panel (blur ~24px, no fill, rounded bottom 16px) over a black/40 blurred page backdrop.
- **Glow:** the 404 gets a soft white double text-shadow (`--nx-glow-404`).
- **Motion:** color fades 200ms; icon cross-fades 300ms with ±90° rotation + scale .75; menu items enter with 400ms ease-out fade + 12px rise, staggered +50ms each starting at 350ms; menu unmounts after 500ms. No bounces, no springs.
- **Hover:** text brightens (white/80→white, white/50→white/80); gradient buttons dim slightly. Press states: none specified.
- **Radii:** pills (9999px) for all buttons; 16px bottom-rounded panels; 6px inputs. No card system — content floats directly on the video; no borders or outer shadows anywhere (only the glass inset highlight).
- **Layout:** root is `relative min-h-screen` flex column; nav / flex-1 centered hero / footer. Breakpoints 640/768/1024. Horizontal page padding 24→48→64px.
- **Imagery:** cool, dark, cinematic space footage. No photos of people, no illustration.

## ICONOGRAPHY

- Icon system is **Lucide** (stroke, 2px, round caps), always small (16–24px) and monochrome white at the text's alpha tier.
- The glyphs the brand uses (arrow-right, menu, x, facebook, twitter, dribbble, youtube, linkedin, instagram) are inlined in the `Icon` component — exact Lucide paths, no hand-drawn substitutes. For anything else, load Lucide from CDN (`https://unpkg.com/lucide@latest`).
- Logo: four white quarter-circle "leaf" shapes forming a circle (`assets/logo.svg`, viewBox 0 0 480 480) + bold tracked "NEXOVA" wordmark. Provided as exact SVG paths in the spec.
- No icon font, no emoji, no unicode-as-icon.

## Components

Bundle namespace: `window.NEXOVADesignSystem_7abf1c`.

- `components/core/` — **Button** (gradient | glass pill), **Icon** (inlined Lucide glyphs), **Logo** (mark + wordmark)
- `components/page/` — **NavBar** (desktop links + animated mobile menu), **Hero404** (light lines, glowing code, glass CTA), **Footer** (4 link columns + newsletter + socials), **BackgroundVideo** (full-bleed loop)

Intentional additions: `Icon` (wrapper for the Lucide glyph set) and `BackgroundVideo` (extracted so any page can reuse the video surface) — both directly implied by the spec.

## Index

- `styles.css` → `tokens/{fonts,colors,typography,effects}.css` + `css/components.css` (all component classes, media queries)
- `assets/logo.svg` — brand mark
- `guidelines/*.html` — specimen cards (colors, type, glass, motion, brand)
- `components/{core,page}/` — JSX + `.d.ts` + `.prompt.md` + card per directory
- `ui_kits/error-404/` — full interactive 404 page recreation
- `SKILL.md` — agent skill entry point

**Caveats:** Helvetica Now Var is hotlinked from onlinewebfonts.com (no font binaries in-project; offline use falls back to Helvetica/Arial). The background video is hotlinked from CloudFront. Only the 404 surface existed in the source — no other product screens were invented.
