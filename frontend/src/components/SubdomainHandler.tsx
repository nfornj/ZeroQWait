import React, { useEffect, useState } from 'react';
import AIShopPublicPage from '../features/public-booking/pages/AIShopPublicPage';
import LandingPage from '../landing-page/LandingPage';
import { getSubdomain } from '../utils/domainUtils';

const SubdomainHandler: React.FC = () => {
    const [subdomain, setSubdomain] = useState<string | null>(null);

    useEffect(() => {
        const sub = getSubdomain();
        if (sub) {
            setSubdomain(sub);
        }
    }, []);

    if (subdomain) {
        return <AIShopPublicPage shopSlug={subdomain} />;
    }

    return <LandingPage />;
};

export default SubdomainHandler;
