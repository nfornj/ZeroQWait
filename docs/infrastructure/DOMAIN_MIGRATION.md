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
- **frontend/src/pages/HomePage.tsx**: Updated brand references throughout
- **frontend/src/pages/WidgetPage.tsx**: Updated footer branding

### Deployment Configuration
- **fly.toml**: Updated app name to `zeroqwait`
- **backend/fly.toml**: Updated app name to `zeroqwait-backend`
- **frontend/fly.toml**: Updated app name to `zeroqwait`

### Documentation
- **README.md**: Updated project name and added live site link
- **WARP.md**: Updated project overview with new domain
- **widget-example.html**: Updated footer link to zeroqwait.com

### Environment Files
- **.env.example**: Added `FRONTEND_URL=https://zeroqwait.com` for production

## Next Steps

### For Development
1. Continue using `localhost:3000` and `localhost:8000` for local development
2. No changes needed to docker-compose.yml or local development workflow

### For Production Deployment

1. **Update Fly.io App Names** (if deploying to Fly.io):
   ```bash
   # You may need to create new apps or rename existing ones:
   fly apps create zeroqwait
   fly apps create zeroqwait-backend
   ```

2. **Set Environment Variables**:
   ```bash
   # Set FRONTEND_URL for production
   fly secrets set FRONTEND_URL=https://zeroqwait.com -a zeroqwait-backend
   ```

3. **DNS Configuration**:
   - Point `zeroqwait.com` to your hosting provider
   - Point `www.zeroqwait.com` to your hosting provider (or redirect)
   - If using Fly.io, add custom domain:
     ```bash
     fly certs add zeroqwait.com -a zeroqwait
     fly certs add www.zeroqwait.com -a zeroqwait
     ```

4. **Deploy**:
   ```bash
   fly deploy -a zeroqwait
   fly deploy -a zeroqwait-backend
   ```

5. **SSL/TLS**:
   - Fly.io automatically provisions SSL certificates
   - Verify HTTPS is working on both domains

## Testing Checklist

After deployment, verify:
- [ ] Frontend loads at https://zeroqwait.com
- [ ] API endpoints are accessible
- [ ] CORS allows requests from zeroqwait.com
- [ ] Password reset emails contain correct domain links
- [ ] Widget embeds work with new domain
- [ ] Both www and non-www domains work
- [ ] SSL certificates are valid

## Rollback Plan

If issues occur, the old configuration references can be found in git history:
```bash
git log --all --full-history -- "*.toml" "*.html" "*.tsx"
```

## Brand Guidelines

**Brand Name**: ZeroQwait (with capital Z and Q)
**Domain**: zeroqwait.com
**Tagline**: Universal queue management for service providers
