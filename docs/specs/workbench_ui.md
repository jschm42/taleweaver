# Workbench UI: one design system for Admin, Editor and Creation

> **Status (2026-11-17):** Phase 0 (foundation) implemented: tokens, Inter, `src/components/ui/`,
> dialogs, toasts, draft model, check script, showcase at `/dev/ui` (dev server only).
> Phases 1–5 open. Agent rules for new work:
> [.claude/rules/frontend-ui.md](../../.claude/rules/frontend-ui.md).

**Scope.** The tool surfaces of TaleWeaver, called the *Workbench* below: the Admin Console
(`AdminView`, `components/admin/`), the Adventure Editor / World-Builder
(`AdventureEditorView`, `components/editor/`), adventure creation (`CreateAdventureView`,
`components/create-adventure/`) and the setup wizard (`components/setup-wizard/`).

**Out of scope.** The play view and its skins (`src/skins/`) and the portal
(`portal-theme.css`). They are atmospheric on purpose. The Workbench shares their brand
colors, not their look.

---

## 1. Findings

Measured on `main` (Nov 2026) across the 126 Workbench `.vue` files (about 39,600 lines).

### 1.1 No shared building blocks

| Building block | Today |
| :--- | :--- |
| Button | 731 `<button>` elements, each styled inline. The most common recipe appears 45 times; there is no `Button` component. |
| Modal | 29 files build their own overlay (`fixed inset-0`), each with its own header, close button, Esc handling and footer. |
| Form field | Labels, hints, counters and errors are written by hand in every form. |
| Toggle | 3 files build a switch from `sr-only peer`; 46 plain checkboxes elsewhere. |
| Help text | 182 `title=` tooltips, an `InfoPopoverButton` that lives in `create-adventure/` only, plus `Info` / `HelpCircle` icons. |
| Feedback | Editor: `NotificationToast` + `addNotification`. Admin: a `statusMessage` banner per service. |
| Questions | 6 native `confirm()` calls (frontend-wide: `ProviderKeysSection`, `PersonalApiKeysCard`, `useEntityTransfer`, `catalogService`, `settingsService`, `userService`) next to hand-made confirmation modals. Removing an API key even asks twice (component and service). |
| Spinner | `ra-cycle`, `ra-recycle`, lucide `Loader2` and a hand-made border spinner. |

### 1.2 No tokens

- `tailwind.config.js` defines an `aether` palette, but the Workbench uses it 10 times. It
  uses raw Tailwind colors instead: slate 902×, emerald 291×, amber 141×, cyan 93×,
  rose 82×, violet 80×, red 60×, blue 50×, purple 32×, indigo 29×, sky 28×, orange 27×, teal 13×.
- Color carries no meaning. The admin sidebar gives each of its 13 entries its own active
  color. Primary buttons are emerald in the editor, purple-to-indigo gradients in
  Intelligence and indigo in Game Settings.
- Panels: at least 8 different surface recipes (`bg-slate-900 border-white/10`,
  `bg-slate-950 border-slate-800`, `bg-slate-950/70 border-white/5`, ...).
- Corners: 9 radii, from `rounded` to `rounded-[2.5rem]`.

### 1.3 Text is too small and too loud

- 933 arbitrary values, almost all font sizes: `text-[10px]` 544×, `text-[11px]` 256×,
  `text-[9px]` 89×, `text-[8px]` 13×, `text-[7px]` 4×. Large parts of the UI are below
  12 px.
- Labels are `font-black uppercase` with five different letter spacings
  (`tracking-widest`, `-wider`, `-[0.2em]`, `-[0.3em]`, `-wide`). When everything is
  shouted, nothing stands out.
- The default font is Acme (`fontFamily.sans`), a display face. Dense forms set in it read
  poorly.

### 1.4 Structure

- **Two different shells.** Admin: fixed sidebar with grouped navigation, page header with
  title + description + save button. Editor: header, an always-visible World-Builder prompt
  above every tab, then a flat list of **18 tabs** in an ungrouped sidebar. Creation and the
  setup wizard follow a third and fourth pattern.
- **Three save models.** Click-to-edit with a save button per field (`WorldTab`,
  `InlineEditableField`), one save button per section (Admin, `PlotTab` with 8 save
  buttons), and modal save (`EditEntityModal`). The user cannot tell what is saved.
- **Monster files.** `AdventureEditorView.vue` 3,609 lines, `EditEntityModal.vue` 2,740
  (its "simple" tab alone is about 1,350 template lines), `SceneRoutePanel` 1,361,
  `ScriptEditor` 1,247, `IntelligenceSection` 1,234, `ValidationTab` 1,068. 16 files are over
  the 600-line limit of `AGENTS.md`.
- **Card in card in card.** Example `GameSettingsSection`: `rounded-3xl` card → `rounded-2xl`
  panel → `rounded-xl` row. Each level adds a border, a background and padding.
- **Three icon systems.** rpg-awesome 290×, lucide in 69 files, 20 inline SVGs.

---

## 2. Principles

1. **Calm tool, rich content.** The Workbench is where authors work for hours. Chrome
   stays quiet (flat surfaces, one accent, no glow, no gradient buttons); images, maps and
   the adventure's own art carry the atmosphere.
2. **Color means something.** Accent = the primary action and the current place. Violet =
   AI does something. Amber = warning, rose = destructive or error, sky = information.
   Nothing else is colored.
3. **One way to do each thing.** One button, one modal, one field, one toast, one save model.
4. **Show the common case, hide the rare one.** Basic fields first; scripts, triggers and
   expert settings behind an "Advanced" disclosure.
5. **Readable first.** Minimum 12 px text, sentence-case labels, visible focus, real
   `<label>`s.

---

## 3. Design Tokens

Tokens are CSS custom properties in a new `src/assets/workbench.css`, mapped into
`tailwind.config.js` under semantic names. Components use the semantic Tailwind classes
only, never raw palette colors.

### 3.1 Color

| Token (Tailwind) | Value (dark) | Use |
| :--- | :--- | :--- |
| `bg-wb-canvas` | `#0b1220` | Page background |
| `bg-wb-surface` | `#111a2b` | Cards, sidebar |
| `bg-wb-raised` | `#172238` | Inputs, hovered rows, popovers |
| `bg-wb-overlay` | `#1d2a43` | Modals, drawers |
| `border-wb-line` | `rgb(255 255 255 / 0.08)` | Every border and divider |
| `border-wb-line-strong` | `rgb(255 255 255 / 0.16)` | Input borders, focus base |
| `text-wb-strong` | `#f1f5f9` | Titles, values |
| `text-wb-body` | `#cbd5e1` | Body text |
| `text-wb-muted` | `#94a3b8` | Hints, secondary text |
| `text-wb-faint` | `#64748b` | Placeholders, disabled |
| `wb-accent` | `#10b981` (aether `primary-container`) | Primary action, active nav, focus ring |
| `wb-ai` | `#8b5cf6` | AI generation, World-Builder, AI fix |
| `wb-info` | `#38bdf8` | Info notes, links |
| `wb-warn` | `#f59e0b` | Warnings, unsaved changes |
| `wb-danger` | `#f43f5e` | Delete, errors |

Each status color comes as `-solid` (buttons), `-soft` (`/12` background) and `-text`
(lighter tint for text on dark).

### 3.2 Type

The Workbench body font changes from Acme to Inter (decision D1). Acme and Cinzel stay for
page titles and adventure names.

| Class | Size / weight | Use |
| :--- | :--- | :--- |
| `wb-title` | 24 px / 700, display font | Page title (one per page) |
| `wb-heading` | 16 px / 600 | Section title |
| `wb-subheading` | 14 px / 600 | Group inside a section |
| `wb-body` | 14 px / 400 | Default text, inputs |
| `wb-label` | 13 px / 500 | Field labels (sentence case) |
| `wb-hint` | 12 px / 400 | Hints, counters, metadata |
| `wb-overline` | 12 px / 600, uppercase, `tracking-wider` | Sidebar group titles only |
| `wb-mono` | 12 px mono | IDs, code, keys |

No other sizes, no `font-black`, no other letter spacing.

### 3.3 Shape, spacing, elevation

- Radius: `rounded-md` (6 px) for controls and badges, `rounded-xl` (12 px) for cards,
  modals and drawers. Nothing else.
- Spacing: 4 px grid. Field gap 16 px, section gap 24 px, card padding 20 px, page padding
  24 px (32 px from `xl`).
- Elevation: cards are flat (border only). Only floating layers (modal, drawer, popover,
  toast) get one shadow token `shadow-wb-float`.
- Icons: lucide for all interface chrome, 16 px in controls, 20 px in headers. rpg-awesome
  only for game content (entity and item types, stats). No inline SVG.

---

## 4. Component Library (`src/components/ui/`)

All components carry the `Ui` prefix, are typed (`defineProps<...>()`), have no business
logic and stay under 200 lines.

| Component | Replaces | Notes |
| :--- | :--- | :--- |
| `UiButton` | 731 inline buttons | Variants `primary`, `secondary`, `ghost`, `danger`, `ai`; sizes `sm`, `md`; `loading`, `icon`, `iconRight`; `type="button"` by default. |
| `UiIconButton` | Close, edit, delete icons | Requires `label` (used for `aria-label` and tooltip). |
| `UiField` | Hand-made labels | `label`, `hint`, `error`, `counter`, `required`, `info` (opens `UiInfoPopover`); wires `id`/`for`/`aria-describedby`. |
| `UiInput`, `UiTextarea`, `UiSelect` | Inline inputs | One look, one focus ring; `UiInput type="number"` yields numbers (`null` when empty); textarea auto-grows. |
| `UiToggle`, `UiCheckbox`, `UiRadioCards` | `sr-only peer` switches, checkboxes, mode tiles | `UiRadioCards` for rule mode, item type and similar choices. |
| `UiCombobox` | `ModelCombobox`, `EntityReferenceCombobox` (base) | Search, keyboard navigation, groups. Not built yet. |
| `UiSpinner` | 4 spinner variants | |
| `UiCard` | 8 panel recipes | Optional header (title, description, actions slot). Never nested. |
| `UiSection` | Page sections | Title, description, actions, `collapsible`, `advanced` (collapsed by default). |
| `UiDisclosure` | Ad-hoc "show more" blocks | Used for "Advanced", "Scripts & triggers". |
| `UiTabs` | Hand-made tab rows | Underline style, keyboard accessible, optional counts. Not built yet (Phase 2). |
| `UiModal` | 29 overlays | Teleport, focus trap, Esc, sizes `sm`/`md`/`lg`, header/body/footer slots, `guardUnsaved`. For short tasks and confirmations. |
| `UiDrawer` | World-Builder prompt block | Slides in from the right, 560–720 px, same slots as `UiModal`. For side panels that keep the page visible (AI panel), not for entity editing. |
| `UiConfirmDialog` + `useConfirm()` | `window.confirm`, custom delete modals | Promise based: `await confirm({ title, body, danger: true })`. One dialog host mounted in `App.vue`, state at module level, so services and composables can ask too. Asks once per action: either the component or the service, not both. |
| `UiPromptDialog` + `usePrompt()` | `window.prompt`, ad-hoc name/value input modals | Promise based: `await prompt({ title, label, initial, validate })`, returns the value or `null`. |
| `UiToast` + `useToast()` | `NotificationToast`, `statusMessage` banners | One queue for the whole app. |
| `UiBadge` | Counters, status chips | Tones `neutral`, `accent`, `ai`, `info`, `warn`, `danger`. |
| `UiEmptyState` | "No items yet" blocks | Icon, text, primary action. |
| `UiSkeleton` | Loading placeholders | Not built yet (Phase 1). |
| `UiInfoPopover` | `InfoPopoverButton`, long help paragraphs | Moved from `create-adventure/`. |
| `UiIdTag` | `object-id-tag`, mono ID chips | Copy on click. Not built yet. |
| `UiSaveBar` | Save buttons per field and section | See 6.1. |

Layout components (`src/components/workbench/`): `WorkbenchShell`, `WorkbenchNav`,
`PageHeader`.

---

### 4.1 Using the foundation

```vue
<script setup lang="ts">
import { useDraft } from '@/composables/useDraft'
import { useUnsavedGuard } from '@/composables/useUnsavedGuard'
import { useConfirm } from '@/composables/useDialogs'
import { useToast } from '@/composables/useToast'

const { draft, isDirty, changedCount, isSaving, reset, commit } = useDraft(() => adventure.value)
useUnsavedGuard(isDirty)
const confirm = useConfirm()
const toast = useToast()

async function save(): Promise<void> {
  await commit((value) => api.updateAdventure(value))
  toast.success('Saved.')
}

async function remove(): Promise<void> {
  if (await confirm({ title: 'Delete this scene?', confirmLabel: 'Delete', danger: true })) {
    await api.deleteScene(id)
  }
}
</script>

<template>
  <div class="wb-root">
    <UiField label="Title" :error="titleError" :count="draft.title.length" :max-length="50">
      <UiInput v-model="draft.title" />
    </UiField>
    <UiSaveBar :dirty="isDirty" :count="changedCount" :saving="isSaving" @save="save" @discard="reset" />
  </div>
</template>
```

- `useConfirm()` / `usePrompt()` and `useToast()` keep their state at module level; services
  may import `confirmDialog`, `promptDialog` and `showToast` directly. `UiDialogHost` and
  `UiToastHost` are mounted once in `App.vue`.
- A page that uses the type scale sets `wb-root` on its root element (Inter, body color).
- Type classes set family and size with normal specificity; weights (except headings) and
  colors use `:where()`, so `text-*` / `font-*` utilities can override them.
- Checks: `npm run lint:ui` (token rules for the folders listed in
  `scripts/check_workbench_ui.mjs` → `MIGRATED`; part of `npm run lint`), eslint `no-alert`
  for native dialogs everywhere. Tests: `tests/workbenchFoundation.test.mjs`.

## 5. Layout and Navigation

### 5.1 One shell

```
┌──────────────┬──────────────────────────────────────────────────────┐
│ ‹ Back       │  Page title                     [secondary] [Primary] │
│ Adventure ▾  │  One line of description                              │
│              ├──────────────────────────────────────────────────────┤
│ STORY        │                                                      │
│  Overview    │   Section                                            │
│  Chapters  3 │   ┌──────────────────────────────────────────────┐   │
│  Side quests │   │ card                                         │   │
│ WORLD        │   └──────────────────────────────────────────────┘   │
│  Map         │                                                      │
│  Scenes  24  │   ▸ Advanced                                         │
│  ...         │                                                      │
│              ├──────────────────────────────────────────────────────┤
│ ✓ Validation │  ● 2 unsaved changes               [Discard] [Save]   │
└──────────────┴──────────────────────────────────────────────────────┘
```

- Sidebar 240 px, grouped, icon + label + optional count badge. Active entry: accent
  background tint and accent text. One color for every entry.
- Below `lg` the sidebar collapses into a menu button; no horizontal tab strip.
- Content width: `max-w-5xl` for forms, full width for map, scripts and tables.
- Page header: title, one-line description, at most one primary and two secondary actions.

### 5.2 Editor navigation (18 tabs → 6 groups)

| Group | Pages |
| :--- | :--- |
| **Story** | Overview (today World), Chapters (Sequences), Side quests, Awards |
| **World** | Map, Scenes, Characters (Inhabitants), Items |
| **Hero** | Protagonist |
| **Logic** | Scripts, Trigger overview, Time & pacing, Dynamic generator |
| **Presentation** | Visual style, Tone, Audio |
| **Settings** | Advanced |

Validation moves to a pinned entry at the bottom of the sidebar with its status badge.
The World-Builder prompt leaves the top of every page and becomes an AI panel: an `ai`
button in the page header and the shortcut `Ctrl+K` open it as a drawer (decision D3).

### 5.3 Admin navigation

| Group | Pages |
| :--- | :--- |
| **Providers** | API keys |
| **AI models** | Intelligence |
| **Media** | Images, Music & audio |
| **Voice** | Text-to-speech, Voice mapping, Speech-to-text |
| **Catalogs** | Image styles, Tones, Narrator personas |
| **System** | Game settings, Users, Setup assistant |

---

## 6. Interaction Patterns

### 6.1 Saving

One model everywhere: **edit freely, save once.**

- A page holds a local draft (`useDraft(source)` composable: `draft`, `isDirty`,
  `changedCount`, `reset()`, `commit()`).
- While dirty, `UiSaveBar` sticks to the bottom: "N unsaved changes · Discard · Save".
  `Ctrl+S` saves. Leaving the page with changes (navigation or route change) asks via
  `useConfirm()`.
- Inline click-to-edit and per-field save buttons go away.
- Exception: actions that are not form edits (generate image, run validation, delete)
  act immediately and confirm destructive steps.

### 6.2 Editing entities

Scenes, characters, items, exits: the list page links to a full **detail page** inside the
shell (decision D2), with its own route (`/editor/:id/characters/:entityId`), so it can be
bookmarked and survives a reload.

- The page header shows a breadcrumb (`Characters › Bram Ironhand`), the entity image and
  ID, and the actions (delete, duplicate, generate image).
- Tabs below the header (`Basics`, `Combat`, `Companion`, `Scripts & triggers`,
  `Advanced`), each tab its own component under 400 lines. The active tab is part of the
  URL.
- The save bar applies to the whole entity across all tabs; leaving with unsaved changes
  asks via `useConfirm()`.
- Previous / next buttons step through the filtered list without going back.
- `EditEntityModal` becomes `EntityDetailPage` + one component per tab and per entity kind;
  `EditExitModal`, the scene and exit route panels follow the same pattern.

### 6.3 Forms

- One column, label above field. Two columns only for short pairs (HP / max HP).
- Every field through `UiField`. Hints at most one sentence; longer explanations go into
  `info` popovers or the docs.
- Group fields with `UiSection` / `wb-subheading`, not with nested cards.
- Validation: inline under the field on blur and on save; the save bar shows the error
  count and blocks saving.

### 6.4 Feedback

- No native browser dialogs. `window.alert`, `window.confirm` and `window.prompt` block the
  page, cannot be styled or tested, and look different in every browser. Every question
  to the user is a Vue dialog: `useConfirm()` for yes/no, `usePrompt()` for a single value,
  a `UiModal`-based component for anything larger. Reuse these before writing a new dialog.
- Success and background results: `useToast()`.
- Errors that block a form: inline + save bar.
- Destructive actions: `useConfirm({ danger: true })`.
- Long-running AI jobs: progress in the page header (`UiBadge tone="ai"` with spinner) and
  a toast on completion; never a pulsing banner.
- Empty lists: `UiEmptyState` with the primary action.

### 6.5 AI actions

Every action that calls an LLM or image model uses the `ai` variant (violet, sparkles icon)
so authors see where cost and latency come from. Results that change content open as a
reviewable proposal (as `WorldBuilderSuggestionsModal` / `AIFixSuggestionsModal` already
do), never as a silent overwrite.

---

## 7. Code Structure

- `views/` only compose: load data, pick the page, hand props down. Target < 300 lines.
- Pages under `components/editor/pages/<Page>Page.vue`, `components/admin/pages/...`.
- State and API calls in composables (`useAdventureDraft`, `useEntityEditor`) or services,
  not in templates.
- Component < 400 lines (warning 600, as `AGENTS.md`). A template longer than about
  150 lines is split.
- No `<style>` blocks for things tokens cover; scoped CSS only for real special cases
  (map canvas, script editor).

---

## 8. Migration

Every phase keeps behavior unchanged and ships on its own. Each PR adds before/after
screenshots.

| Phase | Content | Done when |
| :--- | :--- | :--- |
| **0. Foundation** | `workbench.css` tokens, Tailwind mapping, Inter font, `src/components/ui/` (Button, IconButton, Field, inputs, Toggle, Card, Section, Disclosure, Modal, Drawer, ConfirmDialog, PromptDialog, Toast, Badge, Spinner, EmptyState, InfoPopover), `useDraft`, `useConfirm`, `usePrompt`, `useToast`. Replace every `window.alert` / `confirm` / `prompt` in the frontend. A check script `scripts/check_workbench_ui.mjs` (run in `npm run lint`) that flags native dialogs everywhere, and `text-[Npx]`, hex colors and raw palette colors in migrated folders. | Components exist with a demo route `/dev/ui` (debug only); no native dialog left. |
| **1. Admin (pilot)** | `WorkbenchShell` for Admin, new navigation groups, all admin sections on `Ui*` components and the save bar; `statusMessage` → toasts. | Admin folder passes the check script. |
| **2. Editor shell** | Editor in `WorkbenchShell`, grouped navigation, Validation pinned, World-Builder as AI drawer, `AdventureEditorView` split into pages. | View < 300 lines. |
| **3. Entity editing** | Editor routes for entity detail pages; `EditEntityModal` → `EntityDetailPage` with per-tab components; `EditExitModal`, scene and exit route panels on the same pattern. | No editor file > 600 lines; every entity has a URL. |
| **4. Remaining editor pages** | Scripts, Map, Time, Quests, Awards, Sequences, Audio, Dynamic, Validation on `Ui*` and the draft model. | Editor folder passes the check script. |
| **5. Creation & setup** | `CreateAdventureView` and setup wizard on the same components (`UiRadioCards`, `UiField`). | Whole Workbench passes the check script. |

Folders are added to the check script's list as they are migrated, so finished areas cannot
regress while the rest is still in progress.

---

## 9. Decisions

| # | Question | Decision |
| :--- | :--- | :--- |
| D1 | Workbench body font | **Decided:** self-hosted Inter (`@fontsource/inter`, fallback `ui-sans-serif`). Acme/Cinzel only for page titles and adventure names. |
| D2 | Entity editing: drawer, modal or full page | **Decided:** full detail page with its own route (see 6.2). |
| D3 | Place of the World-Builder prompt | **Decided:** AI drawer opened from the page header and `Ctrl+K`, prefilled with the current page's context. |
| D4 | Light theme | Open. Recommendation: not now; tokens are set up so a light theme is only a second value set. |
