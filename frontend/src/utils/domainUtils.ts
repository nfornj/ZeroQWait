/**
 * domainUtils.ts
 * 
 * Reusable logic for handling subdomains and constructing URLs for the multi-tenant architecture.
 */

// Helper to check if running on localhost
export const isLocalhost = (): boolean => {
    return window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
};

/**
 * Parses the current hostname to extract the subdomain.
 * Returns null if no valid subdomain is found (i.e. we are on the root domain).
 */
export const getSubdomain = (): string | null => {
    const host = window.location.hostname;
    let sub = '';

    if (host.includes('localhost')) {
        // Localhost logic: check for sub.localhost
        const parts = host.split('.');
        if (parts.length > 1) {
            sub = parts[0];
        }
    } else if (host.includes('nip.io')) {
        // nip.io logic (e.g. sub.192.168.2.88.nip.io)
        // Standard nip.io is ip.nip.io (4 parts? no, 192.168.x.x.nip.io)
        // If we have an extra part at the beginning, it's a subdomain.
        const parts = host.split('.');
        // 192.168.x.x.nip.io is 6 parts. sub.192.168.x.x.nip.io is 7 parts.
        // We only want to extract 'sub' if we have 7 or more parts.
        if (parts.length >= 7) {
            sub = parts[0];
        }
    } else if (host.includes('zeroqwait.com')) {
        const parts = host.split('.');
        if (parts.length >= 3) {
            if (parts[0] !== 'www') {
                sub = parts[0];
            }
        }
    } else {
        // Standard domain logic (e.g. other custom domains)
        const parts = host.split('.');
        if (parts.length >= 3) {
            // Check if first part is 'www' - usually treated as root
            if (parts[0] !== 'www') {
                sub = parts[0];
            }
        }
    }

    return sub || null;
};

/**
 * Constructs the full URL for a shop's subdomain.
 * 
 * @param slug - The shop's unique slug
 * @param path - The path to append (e.g. '/ai', '/')
 * @returns The full absolute URL string
 */
export const constructShopUrl = (slug: string, path: string = '/'): string => {
    const protocol = window.location.protocol;
    const host = window.location.host; // includes port if present

    if (isLocalhost()) {
        // On localhost, we can't easily jump to subdomains without config.
        // Fallback to path-based routing for dev ease, OR return relative path if we decide App.tsx handles it.
        // But MasterAIAgent logic was:
        // if localhost -> navigate(`/shop-ai/${shop.id}`) -- wait, slug vs id.
        // Let's standarize on slug where possible, but if dev environment doesn't support wildcards, 
        // we might return a path.

        // HOWEVER, to be "correct" URL generators usually return the target URL.
        // If the caller wants to handle localhost differently, they might check isLocalhost().
        // But let's try to simulate the desired behavior.

        return `${path === '/ai' ? '/shop-ai/' : '/s/'}${slug}`;
    }

    // Production/Staging Logic
    const parts = host.split('.');
    let rootDomain = '';
    const secureProtocol = 'https:'; // Force HTTPS for subdomains

    if (host.includes('nip.io')) {
        // preserve the long tail
        if (parts.length >= 6) rootDomain = parts.slice(-6).join('.');
        else rootDomain = host;
    } else {
        // zeroqwait.com -> take last 2
        rootDomain = parts.slice(-2).join('.');
    }

    return `${secureProtocol}//${slug}.${rootDomain}${path}`;
};
