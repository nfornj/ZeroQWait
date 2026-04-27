// RESTYLED: Perplexity-style
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
                sx={{
                    flexGrow: 1,
                    backgroundColor: theme.palette.background.default,
                    overflow: 'auto',
                    minHeight: '100vh',
                }}
            >
                <Box sx={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'stretch',
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
