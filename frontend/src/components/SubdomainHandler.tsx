import React, { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import AIShopPublicPage from '../features/public-booking/pages/AIShopPublicPage';
import PublicShopPage from '../features/public-booking/pages/PublicShopPage';
import LandingPage from '../landing-page/LandingPage';
import { getSubdomain } from '../utils/domainUtils';

const SubdomainHandler: React.FC = () => {
    const [subdomain, setSubdomain] = useState<string | null>(null);
    const location = useLocation();

    useEffect(() => {
        const sub = getSubdomain();
        if (sub) {
            setSubdomain(sub);
        }
    }, []);

    if (subdomain) {
        if (location.pathname === '/ai' || location.pathname === '/ai/') {
            return <AIShopPublicPage shopSlug={subdomain} />;
        }
        return <PublicShopPage shopSlug={subdomain} />;
    }

    return <LandingPage />;
};

export default SubdomainHandler;
