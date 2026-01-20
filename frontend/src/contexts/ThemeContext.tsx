import React, { createContext, useState, useContext, useEffect, useMemo } from 'react';
import { ThemeProvider as MUIThemeProvider, createTheme, Theme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';

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

export const gradientPresets: Record<GradientPreset, { light: string; dark: string }> = {
    minimal: { light: 'none', dark: 'none' },
    violet: {
        light: 'radial-gradient(ellipse 80% 50% at 50% -20%, hsl(270, 60%, 85%), transparent)',
        dark: 'radial-gradient(ellipse 80% 50% at 50% -20%, hsl(270, 50%, 25%), transparent)',
    },
    ocean: {
        light: 'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
        dark: 'linear-gradient(135deg, #153e40 0%, #2a1b1f 100%)',
    },
    sunset: {
        light: 'linear-gradient(135deg, #f6d365 0%, #fda085 100%)',
        dark: 'linear-gradient(135deg, #3e2b02 0%, #4a1f15 100%)',
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
        // ... (theme creation logic) ...
        // We can inject the gradient into the theme if we want, but keeping it separate is also fine
        return createTheme({
            // ... (existing theme config) ...
            palette: {
                mode,
                primary: {
                    main: themePalettes[themePreset].primary,
                },
                secondary: {
                    main: themePalettes[themePreset].secondary,
                },
                // ...
            },
            // ...
        });
    }, [mode, themePreset]); // Re-create theme only when these change

    return (
        <ThemeContext.Provider value={{ mode, toggleMode, themePreset, setThemePreset, dashboardGradient, setDashboardGradient }}>
            <MUIThemeProvider theme={theme}>
                <CssBaseline />
                {children}
            </MUIThemeProvider>
        </ThemeContext.Provider>
    );
};
