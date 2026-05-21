export const THEME_PRESETS = [
  { id: "default", name: "Coral", primary: "#FF5A5F", secondary: "#00A699" },
  { id: "ocean", name: "Ocean", primary: "#0077B6", secondary: "#48CAE4" },
  { id: "forest", name: "Forest", primary: "#2D6A4F", secondary: "#D8F3DC" },
  { id: "sunset", name: "Sunset", primary: "#E07A5F", secondary: "#F2CC8F" },
  { id: "midnight", name: "Midnight", primary: "#7209B7", secondary: "#4361EE" },
  { id: "corporate", name: "Corporate", primary: "#2B2D42", secondary: "#8D99AE" },
] as const;

export type ThemePreset = (typeof THEME_PRESETS)[number]["id"];

export const themePalettes: Record<ThemePreset, { primary: string; secondary: string }> =
  THEME_PRESETS.reduce((acc, preset) => {
    acc[preset.id] = { primary: preset.primary, secondary: preset.secondary };
    return acc;
  }, {} as Record<ThemePreset, { primary: string; secondary: string }>);

export function themePresetFromColors(
  primary?: string | null,
  secondary?: string | null,
): ThemePreset | null {
  const normalizedPrimary = primary?.toLowerCase();
  const normalizedSecondary = secondary?.toLowerCase();

  const match = THEME_PRESETS.find(
    (preset) =>
      preset.primary.toLowerCase() === normalizedPrimary &&
      preset.secondary.toLowerCase() === normalizedSecondary,
  );

  return match?.id ?? null;
}
