# Domain Migration to zeroqwait.com

This document tracks the migration from the old domain to **zeroqwait.com**.

## Changes Made

### Backend Configuration
- **backend/main.py**: Updated CORS allowed origins to include:
  - `https://zeroqwait.com`
  - `https://www.zeroqwait.com`
- **backend/email_utils.py**: Updated default `FRONTEND_URL` to `https://zeroqwait.com`
- **backend/pyproject.toml**: Updated project name, description, and team email

### Frontend Configuration
- **frontend/public/index.html**: Updated page title and meta description to "ZeroQwait"
- **frontend/public/manifest.json**: Updated app name to "ZeroQwait"
- **frontend/src/components/Navbar.tsx**: Updated brand name display
- **frontend/src/pages/WidgetPage.tsx**: Updated footer branding

### Deployment Configuration
- The active production deployment model is K3s
- The active manifests live under `k8s-manifests/`
- Ingress is handled through Traefik in the `zeroqwait` namespace

### Documentation
- **README.md**: Updated project name and added live site link
- **claude.md**: Maintains the detailed product and deployment context
- **widget-example.html**: Updated footer link to zeroqwait.com

### Environment Files
- `backend/.env` and K8s config determine runtime host configuration

## Next Steps

### For Local Development
1. Use `http://localhost:3000` and `http://localhost:8000`
2. Do not document local development around custom domains unless you are explicitly testing ingress behavior

### For Production Deployment

1. Point `zeroqwait.com` and any required wildcard shop domains at the active ingress
2. Keep the production frontend and API documented as:
   - `https://zeroqwait.com`
   - `https://zeroqwait.com/api`
3. Keep local and test ingress notes separate from production branding
4. Use the production deployment flow defined in `deployment/docs/README.md`

## Testing Checklist

After deployment, verify:
- [ ] Frontend loads at https://zeroqwait.com
- [ ] API endpoints are accessible
- [ ] CORS allows requests from zeroqwait.com
- [ ] Password reset emails contain correct domain links
- [ ] Widget embeds work with new domain
- [ ] Wildcard shop domains route correctly when enabled
- [ ] TLS certificates are valid

## Rollback Plan

If issues occur, the old configuration references can be found in git history:
```bash
git log --all --full-history -- "*.toml" "*.html" "*.tsx"
```

## Brand Guidelines

**Brand Name**: ZeroQwait (with capital Z and Q)
**Domain**: zeroqwait.com
**Product Positioning**: AI operations system for service businesses
