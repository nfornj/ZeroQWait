import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Box, CssBaseline, alpha } from '@mui/material';
import AppNavbar from '../components/dashboard/AppNavbar';
import SideMenu from '../components/dashboard/SideMenu';
import { useThemeContext } from '../contexts/ThemeContext';

const ShopLayout: React.FC = () => {
    // Note: Mobile drawer state is managed inside AppNavbar but SideMenu is for desktop.
    // Template manages mobile drawer via AppNavbar -> SideMenuMobile

    // We need to apply the violet theme background here or in Dashboard.
    // The user wants "exact same template".
    // Template Dashboard.tsx applies background color to Main Content.

    // We will adopt the structure from Dashboard.tsx but as a Layout.

    const { dashboardGradient } = useThemeContext();

    return (
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
    );
};

export default ShopLayout;
