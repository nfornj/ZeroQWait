/**
 * Shared owner-brand token source for shop-aware UI surfaces.
 */
import { alpha, useTheme } from "@mui/material";
import type { PaletteMode } from "@mui/material";

import { useShop } from "../contexts/ShopContext";

export interface OwnerBrandTokens {
  primary: string;
  secondary: string;
  glass: {
    bg: string;
    bgStrong: string;
    border: string;
    shadow: string;
  };
}

export const createOwnerBrandTokens = (
  mode: PaletteMode,
  fallbackPrimary: string,
  primaryColor?: string | null,
  secondaryColor?: string | null,
): OwnerBrandTokens => {
  const primary = primaryColor || fallbackPrimary;
  const secondary = secondaryColor || fallbackPrimary;

  return {
    primary,
    secondary,
    glass: {
      bg: mode === "dark" ? "rgba(255,255,255,0.05)" : alpha("#ffffff", 0.68),
      bgStrong: mode === "dark" ? "rgba(15,18,28,0.82)" : alpha("#ffffff", 0.82),
      border: mode === "dark" ? alpha(primary, 0.24) : alpha(primary, 0.16),
      shadow: `0 18px 60px ${alpha(primary, mode === "dark" ? 0.18 : 0.1)}`,
    },
  };
};

declare module "@mui/material/styles" {
  interface Theme {
    ownerBrand: OwnerBrandTokens;
  }

  interface ThemeOptions {
    ownerBrand?: OwnerBrandTokens;
  }
}

export const useOwnerBrand = (): OwnerBrandTokens => {
  const theme = useTheme();
  const { shop } = useShop();

  return createOwnerBrandTokens(
    theme.palette.mode,
    theme.palette.primary.main,
    shop?.primary_color,
    shop?.secondary_color,
  );
};

export default useOwnerBrand;