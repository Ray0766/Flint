# NEXOVA 404 UI Kit

Pixel recreation of the NEXOVA hosting 404 error page — a single viewport-height layout over a looping Earth-from-space video.

- `index.html` — the full page: `BackgroundVideo` → `NavBar` (with working animated mobile menu below 1024px) → `Hero404` → `Footer`.
- Composes only bundle components (`window.NEXOVADesignSystem_7abf1c`); no local JSX.
- Resize below 1024px to see the hamburger + stagger menu; below 768px/640px for compact hero, footer, and type sizes.
