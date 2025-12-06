# Fly.io Deployment Checklist

Use this checklist to ensure your deployment goes smoothly.

## Pre-Deployment Checklist

### ✅ Files Created/Modified
- [x] `backend/Dockerfile` - Updated for production (removed --reload)
- [x] `backend/fly.toml` - Fly.io backend configuration
- [x] `backend/.dockerignore` - Optimized Docker builds
- [x] `backend/main.py` - Updated CORS for Fly.io domains
- [x] `frontend/Dockerfile` - Updated to accept API URL build arg
- [x] `frontend/fly.toml` - Fly.io frontend configuration
- [x] `frontend/.dockerignore` - Optimized Docker builds
- [x] `frontend/nginx.conf` - Updated for port 8080, added compression
- [x] `frontend/.env.production` - Production environment variables
- [x] `setup-flyio.sh` - Automated setup script
- [x] `deploy.sh` - Quick deployment script
- [x] `FLY_DEPLOYMENT.md` - Comprehensive deployment guide
- [x] `DEPLOYMENT_QUICK_START.md` - Quick start guide

### 📋 Prerequisites
- [ ] Fly.io account created (https://fly.io/app/sign-up)
- [ ] flyctl CLI installed (already installed ✓)
- [ ] Logged into Fly.io (`flyctl auth login`)
- [ ] Supabase credentials ready
- [ ] Email credentials ready (Gmail app password)

### 🔐 Environment Variables Ready
Gather these before running setup:
- [ ] `SECRET_KEY` (JWT signing key)
- [ ] `SUPABASE_URL` (from Supabase dashboard)
- [ ] `SUPABASE_KEY` (service role key)
- [ ] `SUPABASE_ANON_KEY` (anonymous key)
- [ ] `EMAIL_USER` (your Gmail address)
- [ ] `EMAIL_PASSWORD` (Gmail app-specific password)
- [ ] `EMAIL_FROM` (sending email address)

## Deployment Steps

### Option 1: Automated (Recommended)
- [ ] Run `./setup-flyio.sh`
- [ ] Follow the prompts
- [ ] Note the URLs provided at the end

### Option 2: Manual
- [ ] Deploy backend (`cd backend && flyctl launch --no-deploy`)
- [ ] Set backend secrets (`flyctl secrets set ...`)
- [ ] Deploy backend (`flyctl deploy`)
- [ ] Deploy frontend (`cd frontend && flyctl launch --no-deploy`)
- [ ] Deploy frontend with API URL (`flyctl deploy --build-arg REACT_APP_API_URL=...`)

## Post-Deployment Verification

### Backend Tests
- [ ] Test health endpoint: `curl https://your-backend.fly.dev/`
  - Expected: `{"message": "Welcome to Universal Queue System API"}`
- [ ] Check API docs: `https://your-backend.fly.dev/docs`
- [ ] View logs: `cd backend && flyctl logs`
- [ ] Check status: `cd backend && flyctl status`

### Frontend Tests
- [ ] Visit frontend URL in browser
- [ ] Test login functionality
- [ ] Test shop search
- [ ] Test queue joining
- [ ] Check browser console for errors

### Integration Tests
- [ ] Frontend can connect to backend API
- [ ] Authentication works (login/logout)
- [ ] Shop creation and management works
- [ ] Queue operations work
- [ ] Email notifications work

## Configuration Verification

### Backend Configuration
- [ ] Secrets are set: `cd backend && flyctl secrets list`
- [ ] CORS includes frontend URL
- [ ] Health checks working
- [ ] Static uploads directory exists

### Frontend Configuration
- [ ] API URL points to backend
- [ ] Build completed successfully
- [ ] Nginx serving on port 8080
- [ ] React Router working (direct URLs don't 404)

## Cost Optimization

- [ ] `min_machines_running = 0` in fly.toml files (already set ✓)
- [ ] Auto-stop/start enabled (already set ✓)
- [ ] Consider reducing memory if usage is low:
  - Backend: Can reduce from 1GB to 512MB if needed
  - Frontend: Already at 512MB

## Security Checklist

- [ ] All secrets stored in Fly.io secrets (not in fly.toml)
- [ ] CORS only allows specific origins
- [ ] HTTPS enabled (force_https = true)
- [ ] Supabase RLS policies configured
- [ ] Email credentials are app-specific passwords (not main password)

## Monitoring Setup (Optional)

- [ ] Set up Fly.io monitoring dashboard
- [ ] Configure log aggregation
- [ ] Set up uptime monitoring (e.g., UptimeRobot)
- [ ] Configure error alerting

## Custom Domain Setup (Optional)

### Backend
```bash
cd backend
flyctl certs add api.yourdomain.com
# Add CNAME record in your DNS: api.yourdomain.com -> your-backend.fly.dev
```

### Frontend
```bash
cd frontend
flyctl certs add yourdomain.com
# Add CNAME record in your DNS: yourdomain.com -> your-frontend.fly.dev
```

### After Custom Domains
- [ ] Update CORS in backend to include custom frontend domain
- [ ] Update FRONTEND_URL secret in backend
- [ ] Rebuild frontend with custom backend URL
- [ ] Update email templates with custom domain

## Troubleshooting Reference

### Common Issues

**Build Fails**
```bash
flyctl logs --app your-app-name
flyctl deploy --verbose
```

**App Won't Start**
```bash
flyctl ssh console
flyctl secrets list
```

**Connection Issues**
- Check CORS settings in backend
- Verify API URL in frontend
- Check network tab in browser devtools

**Database Issues**
- Verify Supabase credentials
- Check Supabase dashboard for connection limits
- Ensure Supabase project is running

## Rollback Plan

If something goes wrong:

```bash
# View previous releases
flyctl releases

# Rollback to previous version
flyctl releases rollback <version-number>
```

## Next Actions After Successful Deployment

1. **Test Thoroughly**
   - Go through all user flows
   - Test on different devices/browsers
   - Test email notifications

2. **Update Documentation**
   - Document your specific app URLs
   - Update README with production links
   - Document any custom configurations

3. **Set Up CI/CD** (Optional)
   - GitHub Actions for automatic deployments
   - Run tests before deploying
   - Automatic deployments on push to main

4. **Performance Monitoring**
   - Monitor response times
   - Check error rates
   - Monitor resource usage

5. **User Communication**
   - Announce the launch
   - Provide support channels
   - Gather feedback

## Support Resources

- **Quick Start**: See `DEPLOYMENT_QUICK_START.md`
- **Full Guide**: See `FLY_DEPLOYMENT.md`
- **Fly.io Docs**: https://fly.io/docs
- **Fly.io Community**: https://community.fly.io

## Deployment Scripts Reference

```bash
# Initial setup (run once)
./setup-flyio.sh

# Subsequent deployments
./deploy.sh

# View logs
cd backend && flyctl logs
cd frontend && flyctl logs

# Check status
cd backend && flyctl status
cd frontend && flyctl status
```

---

**Ready to deploy?** Start with: `./setup-flyio.sh`
