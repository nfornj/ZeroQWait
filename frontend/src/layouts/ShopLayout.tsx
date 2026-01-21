import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Box, CssBaseline, alpha, ThemeProvider, createTheme, useTheme } from '@mui/material';
import AppNavbar from '../components/dashboard/AppNavbar';
import SideMenu from '../components/dashboard/SideMenu';
import { useThemeContext } from '../contexts/ThemeContext';
import { useShop } from '../contexts/ShopContext';

const ShopLayout: React.FC = () => {
    // Note: Mobile drawer state is managed inside AppNavbar but SideMenu is for desktop.
    // Template manages mobile drawer via AppNavbar -> SideMenuMobile

    // We will adopt the structure from Dashboard.tsx but as a Layout.
    const { shop } = useShop();
    const outerTheme = useTheme();

    const shopTheme = React.useMemo(() => {
        if (!shop?.primary_color) return outerTheme;

        return createTheme(outerTheme, {
            palette: {
                primary: {
                    main: shop.primary_color,
                },
            },
        });
    }, [shop, outerTheme]);

    return (
        <ThemeProvider theme={shopTheme}>
            <Box sx={{ display: 'flex' }}>
                <CssBaseline enableColorScheme />
                <SideMenu />
                <AppNavbar />

                {/* Main Content */}
                <Box
                    component="main"
                    sx={(theme) => ({
                        flexGrow: 1,
                        backgroundColor: theme.vars
                            ? `rgba(${theme.vars.palette.background.defaultChannel} / 1)`
                            : alpha(theme.palette.background.default, 1),
                        overflow: 'auto',
                        minHeight: '100vh',
                    })}
                >
                    <Box sx={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        mx: 3,
                        pb: 5,
                        mt: { xs: 8, md: 0 }, // Top margin for mobile navbar
                        height: '100%',
                    }}>
                        <Outlet />
                    </Box>
                </Box>
            </Box>
        </ThemeProvider>
    );
};

export default ShopLayout;
