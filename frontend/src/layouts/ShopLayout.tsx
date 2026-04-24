import React from 'react';
import { Outlet } from 'react-router-dom';
import { Box, CssBaseline, alpha, useTheme } from '@mui/material';
import AppNavbar from '../features/shop-dashboard/components/AppNavbar';
import SideMenu from '../features/shop-dashboard/components/SideMenu';
import { useOwnerBrand } from '../hooks/useOwnerBrand';

declare module '@mui/material/styles' {
    interface Theme {
        ownerBrand: import('../hooks/useOwnerBrand').OwnerBrandTokens;
    }
}

const ShopLayout: React.FC = () => {
    const theme = useTheme();
    const ownerBrand = useOwnerBrand();
    const brandPrimary = ownerBrand.primary;
    const brandSecondary = ownerBrand.secondary;

    return (
        <Box
            sx={{
                display: 'flex',
                '--owner-primary': brandPrimary,
                '--owner-secondary': brandSecondary,
                '--owner-glass-bg': ownerBrand.glass.bg,
                '--owner-glass-bg-strong': ownerBrand.glass.bgStrong,
                '--owner-glass-border': ownerBrand.glass.border,
                '--owner-glass-shadow': ownerBrand.glass.shadow,
                '& .MuiButton-containedPrimary': {
                    backgroundColor: 'var(--owner-primary)',
                    color: '#fff',
                    boxShadow: '0 10px 26px rgba(0,0,0,0.18)',
                },
                '& .MuiButton-containedPrimary:hover': {
                    backgroundColor: alpha(brandPrimary, 0.86),
                },
                '& .MuiButton-containedSecondary': {
                    backgroundColor: 'var(--owner-secondary)',
                    color: '#fff',
                },
                '& .MuiButton-containedSecondary:hover': {
                    backgroundColor: alpha(brandSecondary, 0.86),
                },
                '& .MuiButton-outlinedPrimary, & .MuiButton-textPrimary': {
                    color: 'var(--owner-primary)',
                    borderColor: alpha(brandPrimary, 0.45),
                },
                '& .MuiButton-outlinedSecondary, & .MuiButton-textSecondary': {
                    color: 'var(--owner-secondary)',
                    borderColor: alpha(brandSecondary, 0.45),
                },
                '& .MuiChip-colorPrimary, & .MuiBadge-colorPrimary .MuiBadge-badge': {
                    backgroundColor: 'var(--owner-primary)',
                },
                '& .MuiChip-colorSecondary, & .MuiBadge-colorSecondary .MuiBadge-badge': {
                    backgroundColor: 'var(--owner-secondary)',
                },
                '& .MuiSvgIcon-colorPrimary': {
                    color: 'var(--owner-primary)',
                },
                '& .MuiSvgIcon-colorSecondary': {
                    color: 'var(--owner-secondary)',
                },
            }}
        >
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
                    backgroundImage:
                        theme.palette.mode === 'light'
                            ? `radial-gradient(circle at 15% 20%, ${alpha(brandPrimary, 0.16)}, transparent 36%), radial-gradient(circle at 85% 0%, ${alpha(brandSecondary, 0.12)}, transparent 35%), linear-gradient(180deg, ${alpha('#ffffff', 0.94)}, ${alpha('#f8fbff', 0.98)})`
                            : `radial-gradient(circle at 15% 20%, ${alpha(brandPrimary, 0.24)}, transparent 36%), radial-gradient(circle at 85% 0%, ${alpha(brandSecondary, 0.18)}, transparent 35%), linear-gradient(180deg, rgba(8,10,18,0.98), rgba(10,12,22,0.98))`,
                    overflow: 'auto',
                    minHeight: '100vh',
                })}
            >
                <Box sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    px: { xs: 1.5, md: 3 },
                    pb: 5,
                    mt: { xs: 8, md: 10 },
                    height: '100%',
                    width: '100%',
                }}>
                    <Outlet />
                </Box>
            </Box>
        </Box>
    );
};

export default ShopLayout;
