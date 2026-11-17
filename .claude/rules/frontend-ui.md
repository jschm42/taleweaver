---
description: Workbench UI rules (Admin, Adventure Editor / World-Builder, adventure creation, setup wizard) - design tokens, shared Ui components, layout, saving and feedback patterns.
trigger: glob
globs: "frontend/src/**/*.vue, frontend/src/**/*.css, frontend/tailwind.config.js"
paths:
  - "frontend/src/**/*.vue"
  - "frontend/src/**/*.css"
  - "frontend/tailwind.config.js"
---

# Workbench UI Guidelines

Rule 3 (no native browser dialogs) applies to the **whole frontend**. All other rules apply
to the tool surfaces: `views/AdminView.vue`, `views/AdventureEditorView.vue`,
`views/CreateAdventureView.vue`, `components/admin/`, `components/editor/`,
`components/create-adventure/`, `components/setup-wizard/`, `components/ui/`,
`components/workbench/`. The play view, its skins (`src/skins/`) and the portal keep their
own atmospheric styling and are not covered here.

Concept, tokens and migration plan: [docs/specs/workbench_ui.md](../../docs/specs/workbench_ui.md).
Until a phase there is done, the code you touch is a mix of old and new. Apply these rules to
everything you **add or change**; do not restyle untouched code in the same task.

## 1. Use the shared components

1. Build with `src/components/ui/` (`UiButton`, `UiIconButton`, `UiField`, `UiInput`,
   `UiTextarea`, `UiSelect`, `UiToggle`, `UiCheckbox`, `UiCard`, `UiSection`,
   `UiDisclosure`, `UiModal`, `UiDrawer`, `UiBadge`, `UiEmptyState`, `UiSpinner`,
   `UiInfoPopover`, `UiSaveBar`, `UiMenu`, `UiNotice`, `UiRadioCards`, `UiSegmented`, `UiIdTag`,
   `UiTabs`, `UiRange`),
   the layout (`WorkbenchShell`, `WorkbenchNav`, `PageHeader`) and the composables `useDialogs` (`useConfirm`,
   `usePrompt`), `useToast`, `useDraft`, `useUnsavedGuard`. Never style a raw `<button>`,
   `<input>` or overlay inline. All components are shown at `/dev/ui` (dev server); the
   admin console (`views/AdminView.vue`, `components/admin/`) is the reference implementation.
2. A component you need does not exist yet: add it to `components/ui/` (typed props, no
   business logic, < 200 lines), then use it. Do not create a local one-off variant.
3. **No native browser dialogs, anywhere in the frontend** (Workbench, play view and
   portal alike). Never use `window.alert`, `window.confirm`, `window.prompt` or their bare
   forms `alert(...)`, `confirm(...)`, `prompt(...)`. Every question to the user is a fully
   implemented Vue dialog:
   - yes/no and destructive confirmations: `useConfirm()` (`UiConfirmDialog`),
   - a single value (name, number, label): `usePrompt()` (`UiPromptDialog`),
   - anything larger: a dialog component built on `UiModal`.
   Reuse these before writing a new dialog; a dialog that several places need goes into
   `components/ui/` (or the area's shared folder for play-view skins), not into the
   calling component. Dialogs are keyboard usable (Enter confirms, Esc cancels, focus is
   trapped and returns to the trigger). Notifications go through `useToast()`; no ad-hoc
   banners or per-component toast state.
4. Icons: lucide for interface chrome, rpg-awesome only for game content (entity types,
   item types, stats). No inline `<svg>`.

## 2. Tokens only

5. Colors only via the semantic `wb-*` classes (`bg-wb-surface`, `text-wb-muted`,
   `border-wb-line`, `wb-accent`, `wb-ai`, `wb-info`, `wb-warn`, `wb-danger`). No raw palette
   classes (`bg-slate-900`, `text-emerald-400`, ...), no hex values, no `bg-[...]`.
6. Color has a meaning: accent = primary action / current place, `ai` = calls an LLM or
   image model, `warn` = warning or unsaved, `danger` = destructive or error, `info` = note.
   Never pick a color for decoration or to tell sections apart.
7. Text only via the type scale (`wb-title`, `wb-heading`, `wb-subheading`, `wb-body`,
   `wb-label`, `wb-hint`, `wb-overline`, `wb-mono`). No `text-[Npx]`, nothing under 12 px,
   no `font-black`, no custom `tracking-*`. Labels are sentence case; uppercase only for
   `wb-overline` (sidebar group titles).
8. Radius `rounded-md` (controls, badges) or `rounded-xl` (cards, modals, drawers). Spacing
   on the 4 px grid. Shadows only on floating layers (`shadow-wb-float`). No gradients,
   glows or `animate-pulse` on Workbench chrome.

## 3. Layout and structure

9. Pages live in `WorkbenchShell` with a `PageHeader` (title, one-line description, at most
   one primary and two secondary actions). New pages go into the sidebar group they belong
   to (see the concept, 5.2 / 5.3); no new top-level tab rows.
10. Never nest cards. Inside a `UiCard`, group with `UiSection`, a `wb-subheading` or a
    divider.
11. Show the common case first. Scripts, triggers and expert options go into a
    `UiDisclosure` labelled "Advanced" or "Scripts & triggers", collapsed by default.
12. Help text: at most one sentence as `hint`. Longer explanations in `UiInfoPopover`
    (`info` prop of `UiField`) or in `docs/`. No `title=` tooltips as the only source of
    help; icon-only buttons need `UiIconButton` with a `label`.
13. Short tasks and confirmations: `UiModal`. Editing an entity (scene, character, item,
    exit): a full detail page with its own route, breadcrumb, tabs in the URL and one
    component per tab, never a modal. `UiDrawer` only for side panels that keep the page
    visible, such as the World-Builder AI panel (`Ctrl+K`).

## 4. Saving and feedback

14. One save model: edit a local draft (`useDraft`), save once through `UiSaveBar` (also
    `Ctrl+S`), discard possible, leaving with changes asks via `useConfirm()`. No
    per-field save buttons and no click-to-edit fields in new code. In the adventure editor,
    pages bind adventure settings directly to `editor.form`; the shell's save bar
    (`useEditorFormDraft`) saves them, and AI text goes into the draft via
    `useFormFieldGenerator`.
15. Actions that are not form edits (generate, validate, delete) run immediately;
    destructive ones confirm with `useConfirm({ danger: true })`.
16. Every list has an empty state (`UiEmptyState`), every async load a `UiSpinner` or
    `UiSkeleton`, every failed request a visible error (inline or toast).
17. AI actions use the `ai` variant and return reviewable proposals; never overwrite
    authored content silently.

## 5. Code size and accessibility

18. Views only compose (target < 300 lines). Components < 400 lines (warning 600). A
    template over ~150 lines is split into child components; logic moves into composables
    or services.
19. Do not add features to oversized files (`composables/editor/useAdventureEditor.ts`,
    `composables/editor/useEntityForm.ts`, `SceneRoutePanel.vue`, `ScriptEditor.vue`,
    `ValidationTab.vue`). Entity form fields go into the matching section component in
    `components/editor/entity/` (state via `useEntityFormContext()`).
    Extract the touched part into a new component or composable first, then change it there.
    New editor pages go into `components/editor/pages/`, read the state with `useEditor()`
    and are registered in `components/editor/editorNavigation.ts`.
20. Every input has a label (`UiField` wires `for` / `aria-describedby`), every button has
    `type="button"` unless it submits, focus stays visible, dialogs trap focus and close on
    Esc.

## 6. Before finishing

21. Run in `frontend/`: `npm run lint:ui` (token check) and eslint on the files you touched
    (`npx eslint <files>`; `npm run lint` also fixes files, so mind unrelated rewrites).
    No new problems; eslint's `no-alert` must stay clean. Run `npm test` when you touched
    logic. When a folder is fully migrated, add it to `MIGRATED` in
    `scripts/check_workbench_ui.mjs`.
22. For visible changes, check the page at 1280 px and at 768 px width, and report what you
    checked. Do not claim a visual result you did not look at.
23. User-facing texts, labels and help are in English and match `docs/`; update in-app help
    and docs in the same task (`AGENTS.md`, rule 4).
