import React, { createContext, useContext, useEffect, useMemo, useState } from "react";

export type ThemePreset = "default" | "ocean" | "forest" | "sunset" | "midnight" | "corporate";
export type ColorMode = "light" | "dark";
export type GradientPreset = "minimal" | "violet" | "ocean" | "sunset";

interface ThemeContextType {
  mode: ColorMode;
  toggleMode: () => void;
  themePreset: ThemePreset;
  setThemePreset: (preset: ThemePreset) => void;
  dashboardGradient: GradientPreset;
  setDashboardGradient: (preset: GradientPreset) => void;
  timeZone: string;
  setTimeZone: (tz: string) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const useThemeContext = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error("useThemeContext must be used within a ThemeProvider");
  }
  return context;
};

const themePalettes: Record<ThemePreset, { primary: string; secondary: string }> = {
  default: { primary: "#7c3aed", secondary: "#9c27b0" },
  ocean: { primary: "#0288d1", secondary: "#26c6da" },
  forest: { primary: "#2e7d32", secondary: "#66bb6a" },
  sunset: { primary: "#ed6c02", secondary: "#ff9800" },
  midnight: { primary: "#311b92", secondary: "#673ab7" },
  corporate: { primary: "#1565c0", secondary: "#42a5f5" },
};

export const gradientPresets: Record<GradientPreset, { light: string; dark: string }> = {
  minimal: { light: "none", dark: "none" },
  violet: {
    light: "radial-gradient(ellipse 80% 80% at 50% -20%, hsl(270, 80%, 78%), hsl(280, 70%, 92%))",
    dark: "radial-gradient(ellipse 80% 80% at 50% -20%, hsl(270, 60%, 20%), hsl(280, 50%, 10%))",
  },
  ocean: {
    light: "linear-gradient(135deg, #67E8F9 0%, #FB7185 100%)",
    dark: "linear-gradient(135deg, #0E7490 0%, #881337 100%)",
  },
  sunset: {
    light: "linear-gradient(135deg, #FCD34D 0%, #FB923C 100%)",
    dark: "linear-gradient(135deg, #78350F 0%, #7C2D12 100%)",
  },
};

function hexToHslComponents(hex: string): string {
  const normalized = hex.replace("#", "");
  const full = normalized.length === 3
    ? normalized.split("").map((char) => char + char).join("")
    : normalized;

  const red = parseInt(full.slice(0, 2), 16) / 255;
  const green = parseInt(full.slice(2, 4), 16) / 255;
  const blue = parseInt(full.slice(4, 6), 16) / 255;
  const max = Math.max(red, green, blue);
  const min = Math.min(red, green, blue);
  const lightness = (max + min) / 2;
  const delta = max - min;

  let hue = 0;
  let saturation = 0;

  if (delta !== 0) {
    saturation = delta / (1 - Math.abs(2 * lightness - 1));
    switch (max) {
      case red:
        hue = ((green - blue) / delta) % 6;
        break;
      case green:
        hue = (blue - red) / delta + 2;
        break;
      default:
        hue = (red - green) / delta + 4;
        break;
    }
  }

  const hueDegrees = Math.round(hue * 60 < 0 ? hue * 60 + 360 : hue * 60);
  return `${hueDegrees} ${Math.round(saturation * 100)}% ${Math.round(lightness * 100)}%`;
}

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [mode, setMode] = useState<ColorMode>(() => {
    const savedMode = localStorage.getItem("themeMode");
    return (savedMode as ColorMode) || "light";
  });

  const [themePreset, setThemePresetState] = useState<ThemePreset>(() => {
    const savedPreset = localStorage.getItem("themePreset");
    return (savedPreset as ThemePreset) || "default";
  });

  const [dashboardGradient, setDashboardGradientState] = useState<GradientPreset>(() => {
    const savedGradient = localStorage.getItem("dashboardGradient");
    return (savedGradient as GradientPreset) || "violet";
  });

  const [timeZone, setTimeZone] = useState<string>(() => {
    return localStorage.getItem("appTimeZone") || Intl.DateTimeFormat().resolvedOptions().timeZone;
  });

  useEffect(() => {
    localStorage.setItem("themeMode", mode);
    document.documentElement.classList.toggle("dark", mode === "dark");
  }, [mode]);

  useEffect(() => {
    localStorage.setItem("themePreset", themePreset);
    const palette = themePalettes[themePreset];
    const rootStyle = document.documentElement.style;
    rootStyle.setProperty("--primary", hexToHslComponents(palette.primary));
    rootStyle.setProperty("--ring", hexToHslComponents(palette.primary));
    rootStyle.setProperty("--owner-primary", palette.primary);
    rootStyle.setProperty("--owner-secondary", palette.secondary);
  }, [themePreset]);

  useEffect(() => {
    localStorage.setItem("dashboardGradient", dashboardGradient);
  }, [dashboardGradient]);

  useEffect(() => {
    localStorage.setItem("appTimeZone", timeZone);
  }, [timeZone]);

  const value = useMemo<ThemeContextType>(
    () => ({
      mode,
      toggleMode: () => setMode((prev) => (prev === "light" ? "dark" : "light")),
      themePreset,
      setThemePreset: setThemePresetState,
      dashboardGradient,
      setDashboardGradient: setDashboardGradientState,
      timeZone,
      setTimeZone,
    }),
    [dashboardGradient, mode, themePreset, timeZone],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};
