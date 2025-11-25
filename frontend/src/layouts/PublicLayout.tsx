import React from 'react';
import { Outlet } from 'react-router-dom';
import Navbar from '../components/Navbar';

const PublicLayout: React.FC = () => {
    return (
        <>
            <Navbar />
            <Outlet />
        </>
    );
};

export default PublicLayout;
