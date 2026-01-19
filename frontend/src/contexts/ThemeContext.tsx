import React, { createContext, useState, useContext, useEffect, useMemo } from 'react';
import { ThemeProvider as MUIThemeProvider, createTheme, Theme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';

// Define available themes
export type ThemePreset = 'default' | 'ocean' | 'forest' | 'sunset' | 'midnight' | 'corporate';
export type ColorMode = 'light' | 'dark';

interface ThemeContextType {
    mode: ColorMode;
    toggleMode: () => void;
    themePreset: ThemePreset;
    setThemePreset: (preset: ThemePreset) => void;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const useThemeContext = () => {
    const context = useContext(ThemeContext);
    if (!context) {
        throw new Error('useThemeContext must be used within a ThemeProvider');
    }
    return context;
};

// Color palettes for different themes
// Each preset defines a primary and potentially secondary color
const themePalettes: Record<ThemePreset, { primary: string; secondary: string; background?: { paper: string, default: string } }> = {
    default: {
        primary: '#FF5A5F', // Coral (Airbnb-ish)
        secondary: '#00A699', // Teal
    },
    ocean: {
        primary: '#0077B6', // Deep Ocean Blue
        secondary: '#48CAE4', // Light Blue
    },
    forest: {
        primary: '#2D6A4F', // Deep Green
        secondary: '#D8F3DC', // Pale Green
    },
    sunset: {
        primary: '#E07A5F', // Terracotta
        secondary: '#F2CC8F', // Gold
    },
    midnight: {
        primary: '#7209B7', // Vibrant Purple
        secondary: '#4361EE', // Blue
    },
    corporate: {
        primary: '#2B2D42', // Dark Slate
        secondary: '#8D99AE', // Greyish Blue
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

    useEffect(() => {
        localStorage.setItem('themeMode', mode);
    }, [mode]);

    useEffect(() => {
        localStorage.setItem('themePreset', themePreset);
    }, [themePreset]);

    const toggleMode = () => {
        setMode((prev) => (prev === 'light' ? 'dark' : 'light'));
    };

    const setThemePreset = (preset: ThemePreset) => {
        setThemePresetState(preset);
    };

    const theme = useMemo(() => {
        const palette = themePalettes[themePreset];

        // Custom background logic for specific themes in dark mode could go here
        // For now we stick to a standard dark/light background unless the theme overrides it strongly

        const lightBackground = { default: '#F7F7F7', paper: '#FFFFFF' };
        const darkBackground = { default: '#121212', paper: '#1E1E1E' };

        // Example: Midnight theme could have a slightly darker blue-ish background in dark mode
        if (themePreset === 'midnight' && mode === 'dark') {
            darkBackground.default = '#0f0c29'; // Deep dark blue/purple
            darkBackground.paper = '#24243e';
        }

        return createTheme({
            palette: {
                mode,
                primary: {
                    main: palette.primary,
                },
                secondary: {
                    main: palette.secondary,
                },
                background: mode === 'light' ? lightBackground : darkBackground,
                text: {
                    primary: mode === 'light' ? '#1C1B1F' : '#E6E1E5', // MD3 Text Colors
                    secondary: mode === 'light' ? '#49454F' : '#CAC4D0',
                },
            },
            typography: {
                fontFamily: '"Roboto", "Inter", "Helvetica", "Arial", sans-serif',
                h1: { fontWeight: 400, fontSize: '3.5rem' }, // MD3 Display Large
                h2: { fontWeight: 400, fontSize: '2.8rem' }, // MD3 Display Medium
                h3: { fontWeight: 400, fontSize: '2.25rem' }, // MD3 Display Small
                h4: { fontWeight: 400, fontSize: '2rem' }, // MD3 Headline Large
                h5: { fontWeight: 400, fontSize: '1.75rem' }, // MD3 Headline Medium
                h6: { fontWeight: 500, fontSize: '1.375rem' }, // MD3 Headline Small
                button: { textTransform: 'none', fontWeight: 500, letterSpacing: '0.1px' },
            },
            shape: {
                borderRadius: 24, // MD3 uses very round corners (e.g. 24px-28px for Large components)
            },
            components: {
                MuiButton: {
                    styleOverrides: {
                        root: {
                            borderRadius: 100, // MD3 pills for buttons
                            height: 40,
                            padding: '0 24px',
                            boxShadow: 'none',
                        },
                        contained: {
                            boxShadow: 'none',
                            '&:hover': {
                                boxShadow: '0px 1px 2px rgba(0,0,0,0.3), 0px 1px 3px 1px rgba(0,0,0,0.15)', // MD3 Elevation 1 on hover
                            }
                        },
                        outlined: {
                            borderWidth: '1px',
                            borderColor: mode === 'light' ? '#79747E' : '#938F99',
                        },
                        text: {
                            padding: '0 12px',
                            borderRadius: 100,
                        }
                    },
                },
                MuiPaper: {
                    styleOverrides: {
                        root: {
                            backgroundImage: 'none',
                        },
                        elevation1: {
                            boxShadow: mode === 'light'
                                ? '0px 1px 2px rgba(0,0,0,0.3), 0px 1px 3px 1px rgba(0,0,0,0.15)'
                                : '0px 1px 2px rgba(0,0,0,0.3), 0px 1px 3px 1px rgba(0,0,0,0.15)', // MD3 Level 1
                        },
                        elevation2: {
                            boxShadow: '0px 1px 2px rgba(0,0,0,0.3), 0px 2px 6px 2px rgba(0,0,0,0.15)', // MD3 Level 2
                        },
                        rounded: {
                            borderRadius: 24, // Consistent card rounding
                        }
                    },
                },
                MuiCard: {
                    styleOverrides: {
                        root: {
                            borderRadius: 24,
                            backgroundColor: mode === 'light' ? '#F7F2FA' : '#25232A', // Surface Container Low/Lowest approximation
                            border: 'none',
                        }
                    }
                },
                MuiTextField: {
                    styleOverrides: {
                        root: {
                            '& .MuiOutlinedInput-root': {
                                borderRadius: 8, // Text fields are usually less rounded (4px-8px) in MD3
                            }
                        }
                    }
                },
                MuiAppBar: {
                    styleOverrides: {
                        root: {
                            backgroundColor: mode === 'light' ? '#F7F2FA' : '#141218',
                            color: mode === 'light' ? '#1C1B1F' : '#E6E1E5',
                            boxShadow: 'none',
                        }
                    }
                },
                MuiDrawer: {
                    styleOverrides: {
                        paper: {
                            backgroundColor: mode === 'light' ? '#F7F2FA' : '#141218',
                            borderRight: 'none',
                            borderRadius: '0 24px 24px 0', // Rounded end of drawer
                        }
                    }
                }
            },
        });
    }, [mode, themePreset]);

    return (
        <ThemeContext.Provider value={{ mode, toggleMode, themePreset, setThemePreset }}>
            <MUIThemeProvider theme={theme}>
                <CssBaseline />
                {children}
            </MUIThemeProvider>
        </ThemeContext.Provider>
    );
};
