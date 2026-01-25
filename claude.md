# Project Rules & Context

## Design System
- **Framework**: Google Material Design 3 (Material You).
- **Implementation**: Use MUI v5+ with rigid MD3 overrides (already configured in `ThemeContext.tsx`).
- **Principles**:
  - **Simplicity**: Interface should be clean and uncluttered.
  - **Component Reuse**: Reuse existing Material Design 3 components; avoid custom CSS where an MUI component suffices.
  - **Styling**: Use the customized `ThemeContext` which provides MD3-compliant border radii (20px+), typography, and elevation. Do not revert to square corners or heavy drop shadows.
