---
name: pinpoint-ui-design
description: Design system and UI conventions for the PINPOINT React frontend (tokens, theming, layout, map and scan screens, states). Use when creating or changing any frontend screen or component.
---

# PINPOINT UI design

This applies the global UI quality bar to PINPOINT. Never ship browser-default screens.

## Foundation

- **Tokens first:** CSS custom properties in `frontend/src/styles/tokens.css` for color, spacing (4 px scale), radius, shadow, type. Tailwind's theme reads these variables; do not hard-code hex values or arbitrary px in components.
- **Themes:** light and dark via `prefers-color-scheme` plus a header toggle (persisted). Test both.
- **One accent color** (a map-pin blue) used for primary actions and the active state only. Semantic colors for status:
  - `active` green, `pending_verification` amber, `rejected` red, `retired`/`merged`/`split` grey.
  - Status is always **color + icon + text**, never color alone.
- **Type:** Inter variable via `@fontsource-variable/inter`, self-hosted. `tabular-nums` for IDs, coordinates and counts. **IDs and coordinates render in a monospace face** with the hyphenated display form and a copy button.
- **Icons:** lucide-react only.

## App shell

Branded header (pin logo, "PINPOINT"), jurisdiction switcher, theme toggle, user menu with role. Left navigation: Map, Places, Review queue (verifiers), Labels, Users (admins), Audit (auditors/admins). Show only what the user's role allows. Content max-width 1280 px, cards with subtle borders. Works from 360 px to wide desktop; the map and scan screens are mobile-first because registrars work in the field.

## Key screens

- **Map:** MapLibre, satellite/street toggle, search by ID or address, cluster markers, side panel with place details. Keyboard-accessible alternative via a coordinates form (see `pinpoint-geo-conventions`).
- **Register place:** stepper (location, details, visibility, review). Live DIGIPIN, locality and duplicate warnings as the pin moves.
- **Place detail:** ID block (copy, QR preview, print label), hierarchy tree (building to units), status pill, history timeline from `place_event`.
- **Scan:** full-screen camera view with a manual-entry fallback that validates the check character as you type. The public resolver page is minimal, branded, and obeys `pinpoint-privacy-india`.
- **Review queue:** list with distance-to-nearest and age; detail with before/after diff and approve/reject (reason required).

## Read-only user view (`viewer`)

Mobile-first, separate shell from the staff app: no left navigation, a simple header, bottom actions. Screens: **Home** (search by ID or place name, "Scan a code", recent lookups, results), and **Place view** (read-only details of a `public` place: ID with copy, address, map with "Open in Maps", units list, a "Read-only" banner, and "Report a problem"). No edit, print, history or status-change controls are rendered for this role (use `RoleGate`; the API enforces it as well). Private places show the minimal "Registered PINPOINT place" page.

## Components and behavior

- Reusable: `StatusPill`, `PlaceIdChip`, `CoordinateText`, `RoleGate`, `MapPinPicker`, `ConfirmDialog`, `Toast`, `Skeleton`, `EmptyState`.
- Buttons: hover, focus-visible, active, disabled and loading states. Segmented controls, tooltips for jargon (DIGIPIN, accuracy, jurisdiction).
- **Every state designed:** skeletons instead of "Loading...", friendly empty states with the next action, inline errors with a recovery step, toasts for results.
- **Destructive or irreversible actions** (retire, merge, split, make public) use a confirm dialog that states the consequence and requires a reason.
- Motion 150-200 ms, disabled under `prefers-reduced-motion`.
- Numbers formatted for India (`en-IN`: lakh/crore grouping where numeric counts are shown, area in sq m).

## Accessibility and security

WCAG AA contrast in both themes, visible focus, labelled form fields, dialogs trap focus, live regions for toasts and scan results (use `react-accessibility-guide`). Never render API strings as HTML; no secrets in `VITE_` variables (use `react-security-guide`).

## Verify before calling UI done

Open it in the browser at 360 px, tablet and desktop, in light and dark, with keyboard only, and check the console for errors. Add component tests (Vitest + RTL) for each new component and a Playwright test for each new flow.
