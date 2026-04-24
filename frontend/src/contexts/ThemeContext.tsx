import React, { createContext, useState, useContext, useEffect, useMemo } from 'react';
import { ThemeProvider as MUIThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';

import { createOwnerBrandTokens } from '../hooks/useOwnerBrand';

// Define available themes
export type ThemePreset = 'default' | 'ocean' | 'forest' | 'sunset' | 'midnight' | 'corporate';
export type ColorMode = 'light' | 'dark';
export type GradientPreset = 'minimal' | 'violet' | 'ocean' | 'sunset';

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
        throw new Error('useThemeContext must be used within a ThemeProvider');
    }
    return context;
};

const themePalettes: Record<ThemePreset, { primary: string; secondary: string }> = {
    default: { primary: '#1976d2', secondary: '#9c27b0' },
    ocean: { primary: '#0288d1', secondary: '#26c6da' },
    forest: { primary: '#2e7d32', secondary: '#66bb6a' },
    sunset: { primary: '#ed6c02', secondary: '#ff9800' },
    midnight: { primary: '#311b92', secondary: '#673ab7' },
    corporate: { primary: '#1565c0', secondary: '#42a5f5' },
};

const appFontFamily = [
    'Inter',
    'Segoe UI',
    'Roboto',
    'Helvetica Neue',
    'Arial',
    'sans-serif',
].join(',');

export const gradientPresets: Record<GradientPreset, { light: string; dark: string }> = {
    minimal: { light: 'none', dark: 'none' },
    violet: {
        light: 'radial-gradient(ellipse 80% 80% at 50% -20%, hsl(270, 80%, 78%), hsl(280, 70%, 92%))',
        dark: 'radial-gradient(ellipse 80% 80% at 50% -20%, hsl(270, 60%, 20%), hsl(280, 50%, 10%))',
    },
    ocean: {
        light: 'linear-gradient(135deg, #67E8F9 0%, #FB7185 100%)',
        dark: 'linear-gradient(135deg, #0E7490 0%, #881337 100%)',
    },
    sunset: {
        light: 'linear-gradient(135deg, #FCD34D 0%, #FB923C 100%)',
        dark: 'linear-gradient(135deg, #78350F 0%, #7C2D12 100%)',
    },
};

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    // Load preferences from localStorage or default
    const [mode, setMode] = useState<ColorMode>(() => {
        const savedMode = localStorage.getItem('themeMode');
        return (savedMode as ColorMode) || 'light';
    });

    const [themePreset, setThemePresetState] = useState<ThemePreset>(() => {
        const savedPreset = localStorage.getItem('themePreset');
        return (savedPreset as ThemePreset) || 'default';
    });

    const [dashboardGradient, setDashboardGradientState] = useState<GradientPreset>(() => {
        const savedGradient = localStorage.getItem('dashboardGradient');
        return (savedGradient as GradientPreset) || 'violet';
    });

    useEffect(() => {
        localStorage.setItem('themeMode', mode);
    }, [mode]);

    useEffect(() => {
        localStorage.setItem('themePreset', themePreset);
    }, [themePreset]);

    useEffect(() => {
        localStorage.setItem('dashboardGradient', dashboardGradient);
    }, [dashboardGradient]);

    const toggleMode = () => {
        setMode((prev) => (prev === 'light' ? 'dark' : 'light'));
    };

    const setThemePreset = (preset: ThemePreset) => {
        setThemePresetState(preset);
    };

    const setDashboardGradient = (preset: GradientPreset) => {
        setDashboardGradientState(preset);
    };

    const theme = useMemo(() => {
        const palettePrimary = themePalettes[themePreset].primary;
        const paletteSecondary = themePalettes[themePreset].secondary;

        return createTheme({
            palette: {
                mode,
                primary: {
                    main: palettePrimary,
                },
                secondary: {
                    main: paletteSecondary,
                },
            },
            ownerBrand: createOwnerBrandTokens(mode, palettePrimary, palettePrimary, paletteSecondary),
            shape: { borderRadius: 10 },
            typography: {
                fontFamily: appFontFamily,
                h1: { fontWeight: 700, letterSpacing: '-0.02em' },
                h2: { fontWeight: 700, letterSpacing: '-0.02em' },
                h3: { fontWeight: 700, letterSpacing: '-0.015em' },
                h4: { fontWeight: 700, letterSpacing: '-0.01em' },
                h5: { fontWeight: 650 },
                h6: { fontWeight: 650 },
                subtitle1: { fontWeight: 600 },
                subtitle2: { fontWeight: 600 },
                body1: { fontWeight: 500 },
                body2: { fontWeight: 500 },
                button: {
                    fontWeight: 600,
                    letterSpacing: '0.01em',
                    textTransform: 'none',
                },
            },
            components: {
                MuiCard: {
                    defaultProps: {
                        elevation: 0,
                    },
                },
                MuiButton: {
                    styleOverrides: {
                        root: {
                            textTransform: 'none',
                            borderRadius: 10,
                        },
                    },
                },
                MuiChip: {
                    styleOverrides: {
                        root: {
                            borderRadius: 8,
                        },
                    },
                },
            },
        });
    }, [mode, themePreset]); // Re-create theme only when these change

    const [timeZone, setTimeZone] = useState<string>(() => {
        return localStorage.getItem('appTimeZone') || Intl.DateTimeFormat().resolvedOptions().timeZone;
    });

    useEffect(() => {
        localStorage.setItem('appTimeZone', timeZone);
    }, [timeZone]);

    return (
        <ThemeContext.Provider value={{ mode, toggleMode, themePreset, setThemePreset, dashboardGradient, setDashboardGradient, timeZone, setTimeZone }}>
            <MUIThemeProvider theme={theme}>
                <CssBaseline />
                {children}
            </MUIThemeProvider>
        </ThemeContext.Provider>
    );
};
