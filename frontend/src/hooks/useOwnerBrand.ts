import { useShop } from "../contexts/ShopContext";
import { useThemeContext } from "../contexts/ThemeContext";

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

function hexAlpha(color: string, opacity: number): string {
  if (color.startsWith("#")) {
    const hex = color.slice(1);
    const full = hex.length === 3
      ? hex.split("").map((c) => c + c).join("")
      : hex;
    const r = parseInt(full.slice(0, 2), 16);
    const g = parseInt(full.slice(2, 4), 16);
    const b = parseInt(full.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
  }
  return `color-mix(in srgb, ${color} ${Math.round(opacity * 100)}%, transparent)`;
}

const DEFAULT_PRIMARY = "#7c3aed";

export type ColorMode = "light" | "dark";

export const createOwnerBrandTokens = (
  mode: ColorMode,
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
      bg: mode === "dark" ? "rgba(255,255,255,0.05)" : hexAlpha("#ffffff", 0.68),
      bgStrong: mode === "dark" ? "rgba(15,18,28,0.82)" : hexAlpha("#ffffff", 0.82),
      border: mode === "dark" ? hexAlpha(primary, 0.24) : hexAlpha(primary, 0.16),
      shadow: `0 18px 60px ${hexAlpha(primary, mode === "dark" ? 0.18 : 0.1)}`,
    },
  };
};

export const useOwnerBrand = (): OwnerBrandTokens => {
  const { mode } = useThemeContext();
  const { shop } = useShop();

  return createOwnerBrandTokens(
    mode,
    DEFAULT_PRIMARY,
    shop?.primary_color,
    shop?.secondary_color,
  );
};

export default useOwnerBrand;
