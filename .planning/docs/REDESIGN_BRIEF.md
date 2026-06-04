# AgentPulse Frontend Redesign — Implementation Brief

A visual mockup is attached: `agentpulse-redesign-mockup.html`. It is a **reference for layout, navigation behavior, typography, and color** — NOT code to copy. Adapt these decisions to our actual stack and component structure. Match the *intent*, not the markup.

## Before you write code
1. Inventory the current frontend: framework, routing, how editions/blocks are fetched and rendered, where global layout/nav lives, current font + color setup.
2. Report back the structure and your implementation plan BEFORE making changes. Do not start editing until the plan is confirmed.
3. Make the change in a branch. Do not touch the publishing pipeline, Supabase, or any backend.

## Goals (in priority order)
1. Consistent, stateful navigation across all sections.
2. Readable long-form typography (stop using monospace for body text).
3. Agent Economy map as a tight grid, not a long vertical scroll.
4. Single coherent color system. Minimalist.

## 1. Navigation
- Persistent top bar on every page: brand (left) · three tabs · Subscribe button (right).
- Three tabs: **Newsletter** / **Agent Economy** / **What is AgentPulse**.
- The tab for the current section is always visually "on" (active state), INCLUDING when viewing a nested page:
  - Inside a single edition/article → Newsletter stays active.
  - Inside a single economy block → Agent Economy stays active.
- "Map" is no longer a plain text link; it is now the "Agent Economy" tab.
- Every nested page (single edition, single block) has a `← Back to [section]` control at top-left.
- Sticky header with subtle blur/translucency is fine; keep it light.

## 2. Mode toggle (Technical / Strategic)
- Lives ONLY inside the Newsletter section (list view and article view).
- Remove it from any global/shared position. It governs newsletter rendering only.
- Active mode shown with filled accent; hint line below ("Architecture, code, implementation" vs "Markets, strategy, implications").

## 3. Typography
- Body / reading text + titles: **Source Serif 4** (editorial serif). Self-host or Google Fonts per our convention.
- Monospace (**IBM Plex Mono**) reserved for UI chrome only: eyebrow label, metadata (Edition # · date), tab labels, buttons, tags, code. NEVER for paragraphs.
- One heading style (serif). Remove the second monospace heading treatment.
- Base body size ~18px, line-height ~1.6.

## 4. Color (light mode, violet accent)
Use CSS variables:
- `--bg:#faf8f5` (warm off-white)
- `--surface:#ffffff`
- `--ink:#1a1916` · `--ink-soft:#55514a` · `--ink-faint:#8a857c`
- `--line:#e7e2da` · `--line-strong:#d8d2c7`
- `--accent:#5b3df5` · `--accent-soft:#efeaff` · `--accent-ink:#4a2fd6`
- One accent only. Use it for links, active tab, card borders, progress dots. No second brand color.
- (If a dark mode exists, defer it — out of scope for this pass. Note it but don't build it.)

## 5. Agent Economy map
- Responsive grid, 2 columns on desktop, 1 on mobile. Tight gaps (~16px).
- Each block = bordered card with: title (serif), one-line description, progress dots.
- Left-border accent on each card (3px, `--accent`).
- Group cards under small mono section labels (e.g. Substrate / Coordination) — use OUR canonical grouping and block list from the data source, not the placeholders in the mockup.
- Deferred/incomplete blocks: span full width, show a "DEFERRED" tag, empty progress dots.
- Hover: subtle lift + shadow. No heavy animation.
- Goal: related blocks visible together, minimal scrolling.

## 6. Spacing & polish
- Tighten the loose vertical gaps from the current site. Minimalist but not sparse.
- Cards, toggle, buttons: ~7–10px radius, consistent.

## Out of scope (do not change)
- Backend, pipeline, Supabase, content/data.
- Dual-mode CONTENT logic (only the toggle's placement/styling changes).
- The About page's deeper content — stub the section with the existing copy; we'll iterate on a pipeline diagram separately.

## Acceptance check
- From any section I can reach any other section in one click, and always know where I am.
- No monospace body paragraphs anywhere.
- Economy map fits more blocks above the fold and shows grouping.
- Back arrow present on every nested page.
- Single accent color throughout.
