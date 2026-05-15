# MUI → shadcn/ui + Tailwind CSS Migration Plan

**Status**: ✅ Migration complete — dashboard, public booking, admin, charts/tables, and theme cleanup migrated  
**Scope**: All authenticated/dashboard surfaces — landing page stays on MUI  
**Goal**: Ultra-modern agent OS aesthetic (Cursor/Linear/Perplexity feel)  
**Approach**: Incremental, phase-by-phase — MUI and shadcn/Tailwind coexist during transition  

---

## Audit Summary

| Metric | Count |
|---|---|
| Files with MUI imports | 112 |
| Total TSX/TS lines | ~38,000 |
| MUI icons used | 85+ unique |
| @mui/x-data-grid usages | 15+ files |
| @mui/x-charts usages | 8+ files |
| @mui/x-tree-view usages | 3 files |
| @mui/x-date-pickers usages | 2 files |

---

## Out of Scope (Keep on MUI — Do Not Touch)

`src/landing-page/` — All files under this directory stay on MUI. The landing page is tightly coupled to `MasterAIAgent.tsx` and the customer-facing SSE chat flow. Migration here is a separate future decision.

---

## Replacement Library Map

| MUI | Replacement |
|---|---|
| `@mui/material` core components | `shadcn/ui` (Radix UI primitives) |
| `@mui/icons-material` | `lucide-react` |
| `@mui/x-charts` (BarChart, LineChart, PieChart, SparkLine) | `recharts` via `shadcn/charts` |
| `@mui/x-data-grid` | `@tanstack/react-table` v8 + shadcn `table` |
| `@mui/x-date-pickers` | `react-day-picker` via shadcn `calendar` + `date-picker` |
| `@mui/x-tree-view` (RichTreeView) | Custom recursive component or `react-arborist` |
| `@emotion/react` + `@emotion/styled` | Tailwind CSS utility classes |
| MUI `ThemeContext` provider | Tailwind + CSS custom properties (lightweight context) |
| MUI `alpha()` for glass effects | Tailwind `bg-white/10`, `backdrop-blur` utilities |
| MUI `styled()` | Tailwind `clsx` + `cn()` helper |

**Keep as-is (not MUI-dependent):**
- `@assistant-ui/react` — wire to shadcn theme in Phase 4
- `@tanstack/react-query`
- `@xyflow/react`
- `react-leaflet`
- `react-markdown`
- `axios` + `src/services/api.ts`
- `AuthContext.tsx`, `ShopContext.tsx` (pure logic)
- All hooks (`useAgentStream`, `useAudioRecorder`, `useAudioVisualizer`, `useApprovalDecisions`, `useAgentWebSocket`)
- `@stripe/react-stripe-js`
- `dayjs`, `date-fns`

---

## Design Tokens (Agent OS Aesthetic)

Set these as CSS custom properties in `src/index.css`. Tailwind config maps to them via `var()`.

```css
/* Dark mode (dashboard default) */
--background: #0a0a0a;
--surface: #111111;
--surface-raised: #1a1a1a;
--border: rgba(255, 255, 255, 0.08);
--border-strong: rgba(255, 255, 255, 0.15);
--text-primary: #f5f5f5;
--text-secondary: #a1a1a1;
--text-muted: #525252;
--accent: #7c3aed;          /* single brand accent — violet */
--accent-foreground: #ffffff;
--success: #22c55e;
--warning: #f59e0b;
--danger: #ef4444;
--glass-bg: rgba(255, 255, 255, 0.04);
--glass-border: rgba(255, 255, 255, 0.08);
```

---

## Phase Breakdown

---

### Phase 1 — Foundation Setup
**Effort**: ~1 day  
**Risk**: Low — additive only, nothing removed  
**Goal**: Install shadcn/ui and Tailwind alongside MUI without breaking anything

#### Steps
1. Install Tailwind CSS v4 and configure `tailwind.config.ts` with content paths covering `src/**/*.{ts,tsx}`
2. Add Tailwind directives to `src/index.css`; define all design token CSS custom properties
3. Install shadcn/ui CLI: `npx shadcn@latest init` — choose dark mode, CSS variables, neutral base
4. Install core shadcn components needed across all phases:
   - `button`, `card`, `input`, `textarea`, `label`
   - `badge`, `separator`, `divider`
   - `sheet`, `dialog`, `drawer`
   - `dropdown-menu`, `context-menu`, `popover`
   - `avatar`, `tooltip`, `skeleton`
   - `scroll-area`, `tabs`
   - `switch`, `checkbox`, `select`
   - `form` (react-hook-form integration)
   - `toast` (sonner)
5. Install `lucide-react`
6. Add `cn()` utility (`src/lib/utils.ts`) — `clsx` + `tailwind-merge`
7. Verify: `npm start` builds without errors, existing MUI pages unaffected

#### Files Created
- `tailwind.config.ts`
- `src/lib/utils.ts`
- `src/components/ui/` — shadcn component folder (auto-generated)
- Updated `src/index.css` — design tokens + Tailwind directives
- Updated `postcss.config.js`

---

### Phase 2 — Layout Shell
**Effort**: 2–3 days  
**Risk**: Medium — layout changes affect all authenticated views  
**Goal**: Replace the navigation chrome (sidebar, navbar, layout wrapper) with shadcn/Tailwind. This is the frame everything else sits inside.

#### Files to Migrate

**`src/layouts/ShopLayout.tsx`** (110 lines)  
- Remove: MUI `Box`, `CssBaseline`, `useTheme`, `alpha`  
- Replace with: Tailwind `div` grid layout, CSS variable brand colors  
- Key behavior to preserve: full-screen agent route, responsive grid, CSS variable injection (`--owner-primary`, `--owner-secondary`, glass effect tokens)

**`src/features/shop-dashboard/components/SideMenu.tsx`**  
- Remove: MUI `Drawer`, `styled`  
- Replace with: shadcn `Sheet` or custom Tailwind sidebar  
- Add: icon-only collapse mode (expand/collapse toggle)

**`src/features/shop-dashboard/components/SideMenuMobile.tsx`**  
- Remove: MUI `Drawer` with `drawerClasses`  
- Replace with: shadcn `Sheet` (side variant) for mobile overlay

**`src/features/shop-dashboard/components/MenuContent.tsx`**  
- Remove: MUI `List`, `ListItem`, `ListItemButton`, `ListItemIcon`, `ListItemText`  
- Replace with: Tailwind nav list, Lucide icons  
- Preserve: active route highlighting, role-based item visibility

**`src/features/shop-dashboard/components/AppNavbar.tsx`** (257 lines)  
- Remove: MUI `AppBar`, `Toolbar`, `Menu`, `Select`, `Avatar`  
- Replace with: Tailwind top bar, shadcn `DropdownMenu`, shadcn `Avatar`  
- Preserve: breadcrumb rendering, shop selector, user menu

**`src/features/shop-dashboard/components/NavbarBreadcrumbs.tsx`**  
- Remove: MUI `Breadcrumbs`, `styled`  
- Replace with: Tailwind breadcrumb (simple `span` + `/` separator)

**`src/features/shop-dashboard/components/OptionsMenu.tsx`**  
- Remove: MUI `Menu`, styled overrides  
- Replace with: shadcn `DropdownMenu`

**`src/features/shop-dashboard/components/MenuButton.tsx`**  
- Remove: MUI `Badge`, `IconButton`  
- Replace with: shadcn `Button` (icon variant) + Tailwind `relative` + badge span

**`src/layouts/PublicLayout.tsx`** (15 lines) — trivial, remove MUI wrapper

#### Verification
- All protected routes render correctly
- Sidebar collapses/expands on desktop
- Mobile drawer opens/closes
- Shop selector in navbar works
- No visual regressions on agent-inbox or dashboard pages (they still use MUI internally at this stage)

---

### Phase 3 — Auth Pages
**Effort**: 2 days  
**Risk**: Low — isolated pages, no shared state complexity  
**Goal**: Clean, minimal auth forms using shadcn

#### Files to Migrate

**`src/features/auth/components/auth-sign-in/SignInCard.tsx`**  
- Remove: MUI `Card`, `TextField`, `Button`, `Checkbox`, `FormControl`, `FormLabel`  
- Replace with: shadcn `Card`, `Input`, `Button`, `Checkbox`, `Label`, `Form`

**`src/features/auth/components/auth-sign-in/SignInSide.tsx`**  
- Remove: MUI `Box`, `Stack`, `CssBaseline`  
- Replace with: Tailwind layout divs

**`src/features/auth/components/auth-sign-up/ShopOwnerSignUp.tsx`** (440 lines)  
- Remove: All MUI form components  
- Replace with: shadcn `Form` + react-hook-form (multi-step wizard pattern)  
- Preserve: 3-step flow (user details → shop details → queue config)

**`src/features/auth/components/auth-sign-up/SignUp.tsx`** (215 lines)  
- Remove: MUI form components  
- Replace with: shadcn `Form`

**`src/features/auth/components/auth-forgot-password/ForgotPassword.tsx`**  
**`src/features/auth/ResetPasswordPage.tsx`**  
- Straightforward form replacements

**`src/features/auth/components/AppTheme.tsx`**  
- This file wraps auth pages in a MUI sub-theme — delete it after migration; auth pages will inherit Tailwind theme

**`src/features/auth/components/customizations/`** (inputs, surfaces, feedback, navigation, dataDisplay, themePrimitives)  
- Delete entire folder once auth pages are migrated — these are MUI-only overrides

**`src/features/auth/components/ColorModeSelect.tsx`** + **`ColorModeIconDropdown.tsx`**  
- Replace with: Tailwind-based toggle if still needed; otherwise remove

#### Verification
- Login flow works end-to-end (submit → JWT → redirect to dashboard)
- Signup flow works (3 steps → shop created → auto-login)
- Password reset email sends
- Form validation shows errors correctly

---

### Phase 4 — Shared Components
**Effort**: 3 days  
**Risk**: Medium — these are used across many features  
**Goal**: Migrate reusable components before migrating the features that use them

#### Files to Migrate

**`src/components/Navbar.tsx`** (323 lines)  
- Remove: MUI icons, any MUI layout components  
- Replace with: Tailwind nav + Lucide icons + shadcn `Button`  
- Preserve: search bar, pricing link, user menu, mobile hamburger

**`src/components/GlassCard.tsx`** (32 lines)  
- Remove: MUI `Card`  
- Replace with: Tailwind div with `bg-white/[0.04] backdrop-blur border border-white/[0.08] rounded-xl`  
- This is a wrapper component — 1 file change removes MUI from every place it's used

**`src/components/AppErrorBoundary.tsx`** (71 lines)  
- Remove: MUI `Alert`, `Box`, `Button`, `Stack`, `Typography`  
- Replace with: shadcn `Alert` + Tailwind layout

**`src/components/ProtectedRoute.tsx`** (36 lines)  
- Remove: MUI `CircularProgress`, `Box`  
- Replace with: shadcn `Skeleton` or Tailwind spinner

**`src/components/DataTable.tsx`** (224 lines)  
- Remove: MUI table (if used) or custom HTML table  
- Replace with: shadcn `Table` + TanStack Table v8 for sorting  
- Preserve: delta formatting, currency formatting, color-coded positive/negative

**`src/components/ProfilePhotoUploader.tsx`** (380 lines)  
- Remove: MUI `Dialog`, `Tabs`, `Tab`, `Button`, `IconButton`, icons  
- Replace with: shadcn `Dialog`, `Tabs`, `Button` + Lucide icons  
- Preserve: webcam capture (react-webcam stays), file drag-and-drop, avatar preview

**`src/components/agent/thread.tsx`** (308 lines) — @assistant-ui chat thread  
- Remove: MUI `Box`, `IconButton`, `Typography`, `alpha`, `useTheme`  
- Replace with: @assistant-ui shadcn theme (`npx assistant-ui add thread`) + Tailwind overrides  
- This is the key @assistant-ui integration point — use official shadcn components

**`src/components/agent/AssistantUIAttachment.tsx`** (337 lines)  
- Remove: MUI icons  
- Replace with: Lucide icons (`Paperclip`, `X`, `File`, `Image`, `FileText`)  
- Preserve: attachment add/remove, preview dialog, file type detection

**`src/hooks/useOwnerBrand.ts`**  
- Remove: `useTheme`, `alpha` from MUI  
- Replace with: read CSS custom properties directly from `document.documentElement` or expose via a lightweight context

#### Verification
- Navbar renders on public pages, user menu works
- Error boundary catches errors and shows fallback
- Protected route shows loading state then renders
- DataTable renders with correct formatting
- ProfilePhotoUploader opens, captures, uploads
- thread.tsx chat renders messages correctly with @assistant-ui

---

### Phase 5 — Agent Inbox (Core Product Surface)
**Effort**: 5–7 days  
**Risk**: High — most complex feature, streaming + real-time + rich content  
**Goal**: The agent inbox is the primary product surface. This phase is the most important visually.

#### Component Order (do in this sequence — dependencies flow top → bottom)

**`src/features/agent-inbox/ThinkingSteps.tsx`** (83 lines) — Start here, smallest  
- Remove: MUI components  
- Replace with: shadcn + Tailwind step indicators  
- Preserve: pending/active/completed states with animations

**`src/features/agent-inbox/ApprovalCard.tsx`** (204 lines)  
- Remove: MUI `Card`, `Button`, icons  
- Replace with: shadcn `Card`, `Button` (approve = default, reject = destructive) + Lucide  
- Design note: this card needs to feel decisive — high contrast, clear action buttons

**`src/features/agent-inbox/AgentFeed.tsx`** (150 lines)  
- Remove: MUI `Badge`, `Chip`, `IconButton`, icons  
- Replace with: shadcn `Badge`, `ScrollArea`, Lucide icons  
- Preserve: event type color coding (chat=blue, tool_call=purple, approval_required=amber, error=red)

**`src/features/agent-inbox/PoliciesPanel.tsx`** (155 lines)  
- Remove: MUI `Switch`, `FormControlLabel`, icons  
- Replace with: shadcn `Switch`, `Label`

**`src/features/agent-inbox/OwnerDocumentsPanel.tsx`** (197 lines)  
- Remove: MUI components  
- Replace with: shadcn `Card`, `Badge`, `Button`

**`src/features/agent-inbox/PendingApprovalsPanel.tsx`** (95 lines)  
- Remove: MUI components  
- Replace with: shadcn `ScrollArea` wrapping migrated `ApprovalCard`

**`src/features/agent-inbox/InsightsPanel.tsx`** (279 lines)  
- Remove: MUI charts, layout components  
- Replace: charts deferred to Phase 6 — use Tailwind placeholders for charts temporarily  
- Migrate: layout, headers, collapse behavior

**`src/features/agent-inbox/OwnerBriefing.tsx`** (211 lines)  
- Remove: MUI `Card`, `Chip`, `Alert`, icons  
- Replace with: shadcn `Card`, `Badge`, Lucide icons  
- Design: clean metric cards — large number, label, trend indicator

**`src/features/agent-inbox/AgentInsights.tsx`** (196 lines)  
- Similar to InsightsPanel — migrate layout, defer chart replacement to Phase 6

**`src/features/agent-inbox/AgentChat.tsx`** (~1,700 lines) — Most complex file  
- Remove: All MUI X Charts (defer to Phase 6 for chart types), MUI layout, MUI icons  
- Wire `@assistant-ui/react` to its native shadcn components (use `thread.tsx` migrated in Phase 4)  
- Replace icons: 13+ MUI icons → Lucide equivalents  
  - `PsychologyAltOutlined` → `Brain`  
  - `MicNoneRounded` → `Mic`  
  - `VolumeUpRounded` → `Volume2`  
  - `UploadFileRounded` → `Upload`  
  - `RefreshRounded` → `RotateCcw`  
  - `StopRounded` → `Square`  
  - `BuildCircleOutlined` → `Wrench`  
- Preserve: SSE streaming, voice mode toggle, file upload, thinking steps, chart/table rendering slots

**`src/features/agent-inbox/AgentInbox.tsx`** (456 lines) — Final assembly  
- Remove: MUI layout, themed wrappers  
- Replace with: Tailwind `grid` layout (70/30 split)  
- Preserve: TanStack Query hooks, WebSocket integration, all panel state logic

#### Verification
- Agent chat streams responses correctly
- Approval cards render and submit approve/reject
- Feed updates in real-time via WebSocket
- Voice mode toggle works (mic → audio recording → SSE with voice)
- File upload to knowledge base works
- Thinking steps animate correctly
- Policy toggles persist

---

### Phase 6 — Charts & Data Tables
**Effort**: 5–6 days  
**Risk**: High — MUI X replacements require careful API mapping  
**Goal**: Replace all @mui/x-charts with Recharts and all @mui/x-data-grid with TanStack Table

#### Step 6a: Charts (Recharts via shadcn/charts)

Install: `recharts` + add shadcn chart components

**Chart API mapping:**

| MUI X Chart | Recharts Equivalent |
|---|---|
| `<BarChart>` | `<BarChart>` + `<Bar>` + `<XAxis>` + `<YAxis>` + `<Tooltip>` |
| `<LineChart>` with area | `<AreaChart>` + `<Area>` |
| `<PieChart>` | `<PieChart>` + `<Pie>` + `<Cell>` |
| `<SparkLineChart>` | `<LineChart>` (simplified, no axes) or `<AreaChart>` (tiny) |

**Files to migrate (charts):**

- `src/features/shop-dashboard/components/PageViewsBarChart.tsx` (BarChart)
- `src/features/shop-dashboard/components/SessionsChart.tsx` (LineChart with area)
- `src/features/shop-dashboard/components/StackedRevenueChart.tsx` (stacked BarChart)
- `src/features/shop-dashboard/components/ChartUserByCountry.tsx` (PieChart + custom SVG)
- `src/features/shop-dashboard/components/StatCard.tsx` (SparkLineChart)
- `src/features/shop-dashboard/components/gridData.tsx` (SparkLineChart instances)
- `src/features/agent-inbox/InsightsPanel.tsx` — chart slots (deferred from Phase 5)
- `src/features/agent-inbox/AgentInsights.tsx` — chart slots (deferred from Phase 5)
- `src/features/agent-inbox/AgentChat.tsx` — inline chart rendering in chat messages

#### Step 6b: Data Tables (TanStack Table + shadcn table)

Install: `@tanstack/react-table`

**Files to migrate (DataGrid → TanStack Table):**

- `src/features/shop-dashboard/components/CustomizedDataGrid.tsx`  
  → TanStack Table + shadcn `Table`, `TableHeader`, `TableBody`, `TableRow`, `TableCell`  
  → Add: column sorting (built into TanStack), filter input above table

- `src/features/shop-dashboard/components/QueueDataGrid.tsx`  
  → Replace `GridActionsCellItem` with shadcn `DropdownMenu` in last column  
  → Preserve: delete and edit actions per row

- `src/features/shop-dashboard/components/RecentVisitsDataGrid.tsx`  
  → Straightforward table — columns: customer, service, time, duration, revenue

- `src/features/shop-dashboard/components/TeamDataGrid.tsx`  
  → Preserve: restore/delete row actions, status badge column

- `src/features/shop-dashboard/pages/ShopSettingsPage.tsx`  
  → Replace embedded DataGrid with shadcn table

**Shared pattern** for all DataGrid replacements:
```
useReactTable({ data, columns, getCoreRowModel, getSortedRowModel, getFilteredRowModel })
→ shadcn Table with header/body/row mapped from table.getHeaderGroups() / table.getRowModel()
→ Lucide sort icon (ChevronUp/ChevronDown) in sortable column headers
→ shadcn DropdownMenu for row actions
```

#### Step 6c: Date Picker

- `src/features/shop-dashboard/components/CustomDatePicker.tsx`  
  → Replace `DatePicker` + `LocalizationProvider` with shadcn `Calendar` + `Popover`  
  → Preserve: custom button trigger (current implementation uses a button to open picker)

- `src/features/shop-dashboard/components/AttendanceCalendar.tsx`  
  → Replace MUI date navigation icons with Lucide `ChevronLeft` / `ChevronRight`

#### Step 6d: Tree View

- `src/features/shop-dashboard/components/CustomizedTreeView.tsx`  
- `src/features/shop-dashboard/components/TeamHierarchy.tsx`  
  → Option A: build a simple recursive Tailwind component (recommended — simple data, not huge trees)  
  → Option B: `react-arborist` if more tree features are needed later  
  → Preserve: expand/collapse, icon per node type, animation

#### Verification
- All charts render with correct data
- Charts are responsive (Recharts `<ResponsiveContainer>`)
- DataGrids render with sorting and filtering working
- Row actions (edit/delete) fire correct callbacks
- Date picker opens, selects date, closes — value propagates to form
- Tree view expands/collapses hierarchy correctly

---

### Phase 7 — Shop Dashboard Pages
**Effort**: 3–4 days  
**Risk**: Medium — these consume components migrated in Phase 6  
**Goal**: Migrate page-level layouts and remaining dashboard components

#### Files to Migrate

**`src/features/shop-dashboard/components/MainGrid.tsx`** (194 lines)  
- Remove: MUI `FormControl`, `Select`, `MenuItem`, `TextField` for date range selector  
- Replace with: shadcn `Select` + Tailwind grid

**`src/features/shop-dashboard/components/StatCard.tsx`** (132 lines)  
- Remove: MUI `Card`, `Chip`, `Stack`  
- Replace with: shadcn `Card` + Tailwind flex + SparkLine (migrated in Phase 6)

**`src/features/shop-dashboard/components/HighlightedCard.tsx`**  
**`src/features/shop-dashboard/components/CardAlert.tsx`**  
- Remove: MUI `Card`, `CardContent`, `Button`  
- Replace with: shadcn `Card` + Tailwind

**`src/features/shop-dashboard/components/Search.tsx`**  
- Remove: MUI `FormControl`, `OutlinedInput`, `InputAdornment`  
- Replace with: shadcn `Input` + Lucide `Search` icon

**`src/features/shop-dashboard/components/OwnerAccountPanel.tsx`**  
- Remove: MUI `Avatar`, `Menu`, `MenuItem`, `ListItemIcon`, `ListItemText`  
- Replace with: shadcn `Avatar`, `DropdownMenu`

**`src/features/shop-dashboard/components/SelectContent.tsx`**  
- Remove: MUI `Avatar`, `Skeleton`, `ListItemAvatar`  
- Replace with: shadcn `Avatar`, `Skeleton`

**`src/features/shop-dashboard/components/ThemeCustomizer.tsx`** (117 lines)  
- Reimagine: color preset picker using Tailwind color swatches  
- Remove: MUI theme coupling  
- Connect to: new lightweight ThemeContext

**`src/features/shop-dashboard/components/EmployeeSelector.tsx`** (220 lines)  
- Remove: MUI dropdown  
- Replace with: shadcn `Select` or `Combobox` with avatar thumbnails

#### Pages (page-level layout cleanup)

**`src/features/shop-dashboard/pages/OwnerDashboardPage.tsx`** (1,077 lines)  
- Remove: MUI layout wrappers, MUI icons  
- Replace with: Tailwind layout divs, Lucide icons  
- Preserve: agent streaming logic, thinking steps, policy management — all non-UI

**`src/features/shop-dashboard/pages/EmployeeQueuePage.tsx`** (683 lines)  
- Migrate layout and status chips to shadcn

**`src/features/shop-dashboard/pages/ShopSettingsPage.tsx`** (653 lines)  
- Remove: MUI forms, DataGrid (done in Phase 6)  
- Replace with: shadcn form sections, Tailwind layout

**`src/features/shop-dashboard/pages/EmployeeManagementPage.tsx`** (429 lines)  
**`src/features/shop-dashboard/pages/AppointmentsPage.tsx`** (366 lines)  
**`src/features/shop-dashboard/pages/QueueManagementPage.tsx`** (309 lines)  
**`src/features/shop-dashboard/pages/ServicesManagementPage.tsx`** (311 lines)  
**`src/features/shop-dashboard/pages/QueueDetailPage.tsx`** (512 lines)  
- Remove: MUI layout + icons  
- Replace with: shadcn + Tailwind + Lucide

#### Verification
- Shop dashboard loads with all stats and charts
- Date range selector changes chart data
- Settings form saves correctly
- Employee CRUD works
- Queue management page loads active queues

---

### Phase 8 — Public-Facing Pages (Booking, Search, Widget)
**Effort**: 3 days  
**Risk**: Medium — these are customer-facing, must work perfectly  
**Goal**: Migrate public booking flow and search to shadcn/Tailwind

#### Files to Migrate

**`src/features/public-booking/AIShopPublicPage.tsx`** (567 lines)  
**`src/features/public-booking/QueueViewPage.tsx`** (706 lines)  
**`src/features/public-booking/PublicShopPage.tsx`** (365 lines)  
**`src/features/public-booking/SearchPage.tsx`** (336 lines)  
**`src/features/public-booking/WidgetPage.tsx`** (344 lines)  
**`src/features/public-booking/InShopDisplayPage.tsx`** (436 lines)  
**`src/features/public-booking/PricingPage.tsx`** (204 lines)  
**`src/features/public-booking/components/HaircutCard.tsx`** (262 lines)  
**`src/features/public-booking/components/MapView.tsx`** (244 lines) — keep react-leaflet, just remove MUI wrappers  
**`src/features/public-booking/components/SearchForm.tsx`** (279 lines)  

- Remove: MUI layout, form components, icons  
- Replace with: shadcn `Card`, `Input`, `Button`, `Badge`, `Select` + Lucide + Tailwind  
- Preserve: Leaflet map integration, WebSocket real-time updates, polling logic

#### Verification
- Search page loads, geocodes location, shows map markers
- Shop card renders correctly, join queue CTA works
- Queue view shows position and ETA, updates in real-time
- In-shop display shows fullscreen queue with pulse animation
- Widget renders cleanly in an iframe

---

### Phase 9 — Admin Portal
**Effort**: 2 days  
**Risk**: Low — admin-only, no customer impact  
**Goal**: Migrate admin panel

#### Files to Migrate

**`src/features/admin/MasterDashboardPage.tsx`** (600+ lines)  
- Remove: MUI `Tab`, `Tabs`, icons, layout components  
- Replace with: shadcn `Tabs` + Tailwind  
- Preserve: shop status overview, feedback review workflow, metrics tabs

#### Verification
- Admin panel loads with correct stats
- Tab navigation works
- Feedback review workflow functions

---

### Phase 10 — ThemeContext Replacement
**Effort**: 1 day  
**Risk**: Low — done last so nothing still depends on MUI theme  
**Goal**: Remove MUI `ThemeProvider` entirely from the dashboard app

#### Steps
1. Replace `src/contexts/ThemeContext.tsx` — remove MUI `ThemeProvider`, `createTheme`, all preset logic
2. New lightweight context: just tracks `mode` (light/dark) in localStorage, applies `class="dark"` to `<html>`
3. Tailwind reads `dark:` variants from the HTML class
4. Color presets: write CSS custom properties directly to `document.documentElement.style` instead of MUI theme
5. Update `src/App.tsx` to remove `<ThemeProvider>` wrapper (keep `<ShopProvider>`, `<AuthProvider>`)
6. Verify landing page still has its own MUI `ThemeProvider` intact (it does — it uses a local `AppTheme.tsx`)

---

### Phase 11 — Cleanup & MUI Removal
**Effort**: 1 day  
**Risk**: Low — cleanup only  
**Goal**: Remove unused MUI packages from package.json

#### Steps
1. Remove from `package.json`:
   - `@mui/x-charts`
   - `@mui/x-data-grid`
   - `@mui/x-date-pickers`
   - `@mui/x-tree-view`
   - `@mui/icons-material`
2. **Keep** in `package.json` (landing page still uses):
   - `@mui/material`
   - `@emotion/react`
   - `@emotion/styled`
3. Run `npm install`, then `npm run build` — fix any remaining import errors
4. Audit `src/` for any stray `@mui/icons-material` or `@mui/x-*` imports that were missed
5. Delete `src/features/auth/components/customizations/` folder (MUI-only overrides, no longer used)
6. Delete `src/features/auth/components/AppTheme.tsx`

#### Verification
- `npm run build` completes with 0 TypeScript errors
- No `@mui/x-*` imports remain outside `landing-page/`
- All dashboard routes load correctly in production build

---

## Icon Replacement Reference (Most Used)

| MUI Icon | Lucide Equivalent |
|---|---|
| `SmartToyRounded` | `Bot` |
| `PsychologyAltOutlined` | `Brain` |
| `AutoAwesomeRounded` | `Sparkles` |
| `MicNoneRounded` | `Mic` |
| `MicOff` | `MicOff` |
| `VolumeUpRounded` | `Volume2` |
| `VolumeOffRounded` | `VolumeX` |
| `SendRounded` | `Send` |
| `StopRounded` | `Square` |
| `RefreshRounded` | `RotateCcw` |
| `UploadFileRounded` | `Upload` |
| `BuildCircleOutlined` | `Wrench` |
| `CheckCircleRounded` | `CheckCircle2` |
| `ErrorOutline` | `AlertCircle` |
| `WarningAmber` | `AlertTriangle` |
| `PendingActions` | `Clock` |
| `ContentCopyRounded` | `Copy` |
| `EditOutlined` | `Pencil` |
| `Delete` | `Trash2` |
| `Add` | `Plus` |
| `Close` | `X` |
| `ExpandMore` | `ChevronDown` |
| `ChevronLeft/Right` | `ChevronLeft/ChevronRight` |
| `Settings` | `Settings` |
| `People` | `Users` |
| `Person` | `User` |
| `Store` | `Store` |
| `Queue` | `List` |
| `Payment` | `CreditCard` |
| `FileDownload` | `Download` |
| `CloudUpload` | `UploadCloud` |
| `Description` | `FileText` |
| `Image` | `Image` |
| `DarkMode` / `LightMode` | `Moon` / `Sun` |
| `RocketLaunchRounded` | `Rocket` |
| `BarChart` | `BarChart2` |
| `InsightsRounded` | `TrendingUp` |

---

## Progress Tracker

| Phase | Description | Status | Est. Days |
|---|---|---|---|
| 1 | Foundation Setup | ✅ Done | 1 |
| 2 | Layout Shell | ✅ Done | 2–3 |
| 3 | Services Page (design validation) | ✅ Done | 1 |
| 4 | Auth Pages | ✅ Done | 2 |
| 5 | Shared Components | ✅ Done | 3 |
| 6 | Agent Inbox | ✅ Done | 5–7 |
| 7 | Charts & Data Tables | ✅ Done | 5–6 |
| 8 | Shop Dashboard Pages | ✅ Done | 3–4 |
| 9 | Public-Facing Pages | ✅ Done | 3 |
| 10 | Admin Portal | ✅ Done | 2 |
| 11 | ThemeContext Replacement | ✅ Done | 1 |
| 12 | Cleanup & MUI Removal | ✅ Done | 1 |
| **Total** | | | **28–33 days** |

Update status to `🔄 In progress` → `✅ Done` as each phase completes.
