import React from 'react';
import Header from '../components/dashboard/Header';
import MainGrid from '../components/dashboard/MainGrid';

const ShopDashboardPage: React.FC = () => {
    return (
        <React.Fragment>
            <Header />
            <MainGrid />
        </React.Fragment>
    );
};

export default ShopDashboardPage;
