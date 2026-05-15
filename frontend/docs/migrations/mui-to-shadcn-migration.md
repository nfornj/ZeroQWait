# MUI to shadcn/Tailwind Migration Audit

**Audit date:** 2026-05-09  
**Status:** Complete: frontend source and direct dependencies no longer use MUI or Emotion.

## Summary

The frontend is configured for shadcn/ui and Tailwind CSS, and the previously remaining landing page and customer-facing chat surface have now been migrated. `MasterAIAgent` no longer imports MUI or MUI X Charts; charts now render through Recharts with the shadcn chart wrapper.

Generated output such as `build/` and third-party dependencies such as `node_modules/` were excluded from this audit. `MIGRATION.md` is treated as historical context; this file reflects the current repository state as of May 9, 2026.

## Completed Checklist

- [x] shadcn project configured via `components.json`.
- [x] Tailwind v3 configured via `tailwind.config.js` and `src/index.css`.
- [x] shadcn UI components installed under `src/components/ui`.
- [x] `src/contexts/ThemeContext.tsx` no longer uses MUI; it writes Tailwind CSS variables and toggles `.dark`.
- [x] No active `@mui/x-data-grid`, `@mui/x-date-pickers`, or `@mui/x-tree-view` imports remain.
- [x] Dashboard, shop management, agent inbox, agent brain, admin, auth sign-in/sign-up, in-shop display, and public booking/search/pricing source areas are migrated to Tailwind/shadcn patterns.
- [x] `src/landing-page/` migrated from MUI to shadcn/Tailwind.
- [x] `src/landing-page/components/MasterAIAgent.tsx` migrated from MUI and `@mui/x-charts` to shadcn/Tailwind and Recharts.
- [x] Landing page MUI icons replaced with `lucide-react`.
- [x] Landing MUI theme wrapper usage from `src/features/auth/components/auth-shared-theme` removed.
- [x] `src/features/auth/components/auth-shared-theme/**` removed after landing no longer imported it.
- [x] Stale MUI README note removed from `src/features/auth/components/auth-sign-in/README.md`.
- [x] Remaining MUI/Emotion direct dependencies removed: `@mui/material`, `@mui/icons-material`, `@mui/x-charts`, `@emotion/react`, and `@emotion/styled`.
- [x] `react-is` added as an explicit dependency for Recharts production builds.
- [x] `npm run typecheck` passes.
- [x] `npm run build` succeeds.

## Remaining Checklist

- [x] No remaining MUI migration items found in active frontend source or direct frontend dependencies.

## Active MUI Source Files

None found by the active source scan.

## Transitive And Dependency Notes

- `src/features/public-booking/pages/AIShopPublicPage.tsx` still imports `MasterAIAgent`, but `MasterAIAgent` is now implemented with shadcn/Tailwind and no longer transitively activates MUI.
- `package.json` and `package-lock.json` no longer include direct MUI or Emotion packages.
- `@mui/x-charts` was removed; landing/customer chat charts now use Recharts.

## Verification Commands

These commands were used for the final audit:

```bash
npx shadcn@latest info
rg -n --hidden -g '!node_modules' -g '!build' -g '!dist' '@mui|@emotion|@mui/x-charts|mui/material|mui/icons' src package.json package-lock.json
rg -n '@mui/x-data-grid|@mui/x-date-pickers|@mui/x-tree-view|DataGrid|DatePicker|RichTreeView' src package.json
npm ls @mui/material @mui/icons-material @mui/x-charts @emotion/react @emotion/styled --depth=0
npm run typecheck
npm run build
```

## Current Verification Results

- `npx shadcn@latest info` reports a manual TypeScript project using Tailwind v3, Radix base, lucide icons, and `@/components/ui` as the UI alias.
- The active MUI/Emotion source scan returns no matches.
- No active `@mui/x-data-grid`, `@mui/x-date-pickers`, or `@mui/x-tree-view` imports remain; the broad scan still finds local component names such as `QueueDataGrid`, `TeamDataGrid`, and `CustomDatePicker`.
- `npm ls` reports none of `@mui/material`, `@mui/icons-material`, `@mui/x-charts`, `@emotion/react`, or `@emotion/styled` installed as direct frontend dependencies.
- `npm run typecheck` completes successfully.
- `npm run build` completes successfully. The build still reports pre-existing warnings in unrelated non-landing files.
