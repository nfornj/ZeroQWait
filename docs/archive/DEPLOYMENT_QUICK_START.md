# Quick Start: Deploy to Fly.io

This guide will get your Nowait application deployed to Fly.io in minutes.

## Option 1: Automated Setup (Recommended)

Run the automated setup script that will guide you through the entire process:

```bash
./setup-flyio.sh
```

This script will:
1. Check if flyctl is installed (install if needed)
2. Log you into Fly.io
3. Create and deploy the backend app
4. Set up all required environment variables
5. Create and deploy the frontend app
6. Give you the URLs for both apps

**That's it!** Your app will be live on Fly.io.

## Option 2: Manual Setup

If you prefer to do it manually, follow the detailed instructions in [FLY_DEPLOYMENT.md](FLY_DEPLOYMENT.md).

### Quick Manual Steps:

1. **Login to Fly.io**
   ```bash
   flyctl auth login
   ```

2. **Deploy Backend**
   ```bash
   cd backend
   flyctl launch --no-deploy
   # Set your secrets (see FLY_DEPLOYMENT.md for details)
   flyctl secrets set SECRET_KEY="..." SUPABASE_URL="..." SUPABASE_KEY="..." ...
   flyctl deploy
   cd ..
   ```

3. **Deploy Frontend**
   ```bash
   cd frontend
   flyctl launch --no-deploy
   flyctl deploy --build-arg REACT_APP_API_URL=https://your-backend.fly.dev/api
   cd ..
   ```

## Future Deployments

After initial setup, use the deployment script:

```bash
./deploy.sh
```

This will let you quickly redeploy either backend, frontend, or both.

## What's Been Configured

Your application is now production-ready with:

✅ **Backend (FastAPI)**
- Production-ready Dockerfile (no auto-reload)
- Fly.io configuration with health checks
- CORS properly configured for Fly.io domains
- Environment variables via Fly.io secrets
- Auto-stop/start to save costs

✅ **Frontend (React + Nginx)**
- Production build with optimization
- Nginx configured for port 8080
- Gzip compression enabled
- React Router support
- Static asset caching
- Build-time API URL configuration

✅ **Infrastructure**
- Separate backend and frontend apps
- Using existing Supabase database
- Minimal resource allocation (cost-effective)
- Auto-scaling capabilities

## Costs

Fly.io free tier includes:
- 3 shared-cpu-1x VMs with 256MB RAM
- 3GB persistent storage
- 160GB outbound data transfer

Your setup uses:
- Backend: 1 VM with 1GB RAM
- Frontend: 1 VM with 512MB RAM

Both apps are configured to auto-stop when idle and auto-start on requests, which helps manage costs.

## Useful Commands

```bash
# View logs
cd backend && flyctl logs
cd frontend && flyctl logs

# Check status
cd backend && flyctl status
cd frontend && flyctl status

# Update secrets
cd backend && flyctl secrets set SECRET_KEY="new-value"

# SSH into a running instance
cd backend && flyctl ssh console

# Scale resources
cd backend && flyctl scale vm shared-cpu-1x --memory 512
```

## Troubleshooting

### Build fails
- Check logs: `flyctl logs`
- Try verbose deploy: `flyctl deploy --verbose`

### App won't start
- Check if secrets are set: `flyctl secrets list`
- Verify Supabase connection
- Check CORS configuration

### Frontend can't connect to backend
- Verify API URL in frontend build
- Check backend CORS settings
- Ensure both apps are deployed

## Need Help?

- Full documentation: [FLY_DEPLOYMENT.md](FLY_DEPLOYMENT.md)
- Fly.io docs: https://fly.io/docs
- Check logs for detailed error messages

## Next Steps

After deployment:
1. ✅ Test all features on production
2. 🌐 Set up custom domains (optional)
3. 📊 Configure monitoring
4. 🔄 Set up CI/CD for automatic deployments
5. 📧 Update email templates with production URLs
