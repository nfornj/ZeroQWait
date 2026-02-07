import React from 'react';
import Stack from '@mui/material/Stack';
import Header from '../components/Header';
import MainGrid from '../components/MainGrid';

const ShopDashboardPage: React.FC = () => {
    return (
        <Stack spacing={2} sx={{ width: '100%', pb: 4, px: 3 }}>
            <Header />
            <MainGrid />
        </Stack>
    );
};

export default ShopDashboardPage;
