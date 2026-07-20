# Design System Master File

> **LOGIC:** When building a specific page, first check `design-system/pages/[page-name].md`.
> If that file exists, its rules **override** this Master file.
> If not, strictly follow the rules below.

---

**Project:** Virtus et Veritas Engine
**Generated:** 2026-07-19
**Category:** Premium / Academic Authority (dark mode)

**Adaptation note:** the raw `--design-system` search returned a light-mode, single-page
"Liquid Glass" landing-page pattern (Luxury/Premium Brand match). This app is a dense,
multi-screen dark-mode product (dashboards, tables, forms, sidebar nav) — the palette
below was manually inverted to dark mode, the heavy blur/morphing effects were dropped
(poor performance + contrast risk per the tool's own warning), and typography was
re-picked for UI legibility instead of landing-page display type. Chosen direction:
"Preto & Ouro Premium" (warm near-black + darker gold), selected by the user from 4
palette options.

---

## Global Rules

### Color Palette (dark mode, warm neutral base)

| Role | Hex | CSS Variable | Usage |
|------|-----|--------------|-------|
| Background | `#1C1917` | `--color-background` | page background |
| Surface | `#23201D` | `--color-surface` | sidebar, topbar |
| Card | `#2B2723` | `--color-card` | cards, panels, modals |
| Border | `#3D3833` | `--color-border` | dividers, input borders |
| Foreground | `#FAFAF9` | `--color-foreground` | primary text |
| Muted Foreground | `#A8A29E` | `--color-muted-foreground` | secondary text, captions |
| Accent / CTA (button bg) | `#A16207` | `--color-accent` | primary buttons, active nav, focus ring |
| Accent text (on dark bg) | `#D9A441` | `--color-accent-foreground-on-dark` | gold used as text/label, not as a button fill |
| On Accent | `#FFFFFF` | `--color-on-accent` | text/icons on top of accent buttons |
| Success | `#22C55E` | `--color-success` | positive status |
| Destructive | `#EF4444` | `--color-destructive` | errors, destructive actions |
| Ring | `#A16207` | `--color-ring` | focus outline |

**Color Notes:** Same family as the current `navy`/`gold` tokens but replacing the blue-black
with a warm neutral black (less "tech/SaaS", more "premium academy"), and splitting gold into
two tokens — a darker one for button fills and a lighter tint for gold *text* on dark
backgrounds (a single gold value can't satisfy both contrast needs).

### Typography

- **Heading / Display Font:** Jost (geometric, distinctive, premium — used for H1/H2, logo, large stats)
- **Body / UI Font:** Inter (proven legibility at small sizes — forms, tables, nav, buttons, body text)
- **Mood:** premium, minimalist, sophisticated, but legible in dense screens
- **Why not Bodoni Moda (the tool's raw suggestion):** it's a high-contrast display serif built
  for fashion/luxury headlines, not for a data-dense app with tables and forms at 14–16px —
  swapped in Inter for anything that isn't a large heading.
- **Google Fonts:** [Jost + Inter](https://fonts.googleapis.com/css2?family=Jost:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap)

**CSS Import:**
```css
@import url('https://fonts.googleapis.com/css2?family=Jost:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap');
```

### Spacing Variables

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | `4px` / `0.25rem` | Tight gaps |
| `--space-sm` | `8px` / `0.5rem` | Icon gaps, inline spacing |
| `--space-md` | `16px` / `1rem` | Standard padding |
| `--space-lg` | `24px` / `1.5rem` | Section padding |
| `--space-xl` | `32px` / `2rem` | Large gaps |
| `--space-2xl` | `48px` / `3rem` | Section margins |
| `--space-3xl` | `64px` / `4rem` | Hero/empty-state padding |

### Shadow Depths

| Level | Value | Usage |
|-------|-------|-------|
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.24)` | Subtle lift |
| `--shadow-md` | `0 4px 6px rgba(0,0,0,0.32)` | Cards, buttons |
| `--shadow-lg` | `0 10px 15px rgba(0,0,0,0.36)` | Modals, dropdowns |
| `--shadow-xl` | `0 24px 80px rgba(0,0,0,0.42)` | Featured cards, dialogs |

---

## Component Specs

### Buttons

```css
.btn-primary {
  background: var(--color-accent);
  color: var(--color-on-accent);
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 600;
  transition: background-color 200ms ease, transform 150ms ease;
  cursor: pointer;
}
.btn-primary:hover { background: #B8770D; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }

.btn-secondary {
  background: transparent;
  color: var(--color-foreground);
  border: 1px solid var(--color-border);
  padding: 10px 20px;
  border-radius: 8px;
  font-weight: 500;
  transition: border-color 200ms ease;
  cursor: pointer;
}
.btn-secondary:hover { border-color: var(--color-accent); }
```

### Cards

```css
.card {
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 20px;
  transition: border-color 200ms ease;
}
.card:hover { border-color: var(--color-accent); } /* only for clickable cards */
```

### Inputs

```css
.input {
  background: var(--color-background);
  color: var(--color-foreground);
  border: 1px solid var(--color-border);
  padding: 10px 14px;
  border-radius: 8px;
  font-size: 16px; /* never below 16px: prevents iOS zoom-on-focus */
  transition: border-color 150ms ease;
}
.input:focus {
  border-color: var(--color-accent);
  outline: none;
  box-shadow: 0 0 0 3px rgba(161, 98, 7, 0.25);
}
```

### Status badges

```css
.badge-success { background: rgba(34,197,94,0.12); color: #4ADE80; border: 1px solid rgba(34,197,94,0.3); }
.badge-warning { background: rgba(161,98,7,0.12); color: var(--color-accent-foreground-on-dark); border: 1px solid rgba(161,98,7,0.3); }
.badge-error   { background: rgba(239,68,68,0.12); color: #F87171; border: 1px solid rgba(239,68,68,0.3); }
```

### Modals

```css
.modal-overlay { background: rgba(0, 0, 0, 0.6); }
.modal {
  background: var(--color-card);
  border: 1px solid var(--color-border);
  border-radius: 16px;
  padding: 28px;
  max-width: 520px;
  width: 90%;
}
```

---

## Style Guidelines

**Style:** Premium Academic Authority (dark, warm-neutral, restrained)

**Keywords:** warm black, gold accent, generous spacing, quiet confidence, no gradients-for-gradients-sake

**Best For:** professional/corporate education tooling, admin/creator dashboards, enterprise SaaS

**Key Effects (kept deliberately restrained — this is a functional app, not a marketing page):**
- Border-color transitions on hover (150–200ms), not scale/shadow-heavy motion
- No `backdrop-filter` blur on anything performance-sensitive (tables, lists) — reserve blur for
  the rare full-screen modal overlay only
- No morphing/gradient-shifting effects — they read as decorative noise in a data-dense app

### Page Pattern

This app is **sidebar + content**, not a single-column landing page — the tool's "Minimal
Single Column" pattern does not apply here. Structure to follow across all authenticated
screens: fixed left sidebar (nav) → topbar (user/org context) → content area with page
header (eyebrow + H1 + short description) → primary content block(s).

---

## Anti-Patterns (Do NOT Use)

- ❌ Heavy blur/morphing/"Liquid Glass" effects (performance + contrast risk, wrong genre for this app)
- ❌ Emojis as icons — use SVG icons (Heroicons/Lucide), consistent set across the app
- ❌ Missing `cursor: pointer` on clickable elements
- ❌ Layout-shifting hover transforms (scale/translate that reflows neighbors)
- ❌ Low contrast text — maintain 4.5:1 minimum, check gold-on-dark specifically (use
  `--color-accent-foreground-on-dark`, not `--color-accent`, for gold text)
- ❌ Instant state changes — always transition 150–300ms
- ❌ Invisible focus states — keyboard focus must be visible (use `--color-ring`)
- ❌ Raw hex colors in components — always reference the CSS variables/Tailwind tokens above

---

## Pre-Delivery Checklist

Before delivering any UI page/component, verify:

- [ ] No emojis used as icons (SVG only, consistent icon set)
- [ ] `cursor-pointer` on all clickable elements
- [ ] Hover/focus states with smooth transitions (150–300ms)
- [ ] Text contrast 4.5:1 minimum (gold text uses the *light* gold token, not the button gold)
- [ ] Focus states visible for keyboard navigation
- [ ] `prefers-reduced-motion` respected
- [ ] Responsive: 375px, 768px, 1024px, 1440px
- [ ] No content hidden behind fixed sidebar/topbar
- [ ] No horizontal scroll on mobile
- [ ] Every raw color reference replaced with a token from this file
