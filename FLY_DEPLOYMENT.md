# Fly.io Deployment Guide

This guide will help you deploy the Nowait application to Fly.io.

## Prerequisites

1. Install the Fly CLI: `brew install flyctl` (already installed ✓)
2. Create a Fly.io account: https://fly.io/app/sign-up
3. Login to Fly.io: `flyctl auth login`

## Deployment Steps

### 1. Deploy Backend

```bash
cd backend

# Launch the backend app (this will create the app on Fly.io)
flyctl launch --no-deploy

# When prompted:
# - Use the app name: nowait-backend (or choose your own)
# - Choose a region (closest to your users)
# - DO NOT add a PostgreSQL database (you're using Supabase)
# - DO NOT deploy yet

# Set secrets (environment variables)
flyctl secrets set \
  SECRET_KEY="09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7" \
  SUPABASE_URL="https://yuxfpspyzyhesfuspjns.supabase.co" \
  SUPABASE_KEY="your-supabase-service-role-key" \
  SUPABASE_ANON_KEY="your-supabase-anon-key" \
  EMAIL_HOST="smtp.gmail.com" \
  EMAIL_PORT="587" \
  EMAIL_USER="nfornj@gmail.com" \
  EMAIL_PASSWORD="your-email-app-password" \
  EMAIL_FROM="nfornj@gmail.com" \
  FRONTEND_URL="https://nowait-frontend.fly.dev"

# Deploy the backend
flyctl deploy

# Note your backend URL (e.g., https://nowait-backend.fly.dev)
```

### 2. Update Backend CORS Settings

After deploying the backend, update the CORS origins in `backend/main.py` to include your Fly.io frontend URL:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://nowait-frontend.fly.dev"  # Add your frontend URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Then redeploy the backend:
```bash
cd backend
flyctl deploy
```

### 3. Deploy Frontend

```bash
cd ../frontend

# Launch the frontend app
flyctl launch --no-deploy

# When prompted:
# - Use the app name: nowait-frontend (or choose your own)
# - Choose the same region as backend
# - DO NOT add a database
# - DO NOT deploy yet

# Set the backend API URL as a build argument
# You need to add this to the frontend Dockerfile as a build-time variable
# Or set it in fly.toml

# Deploy the frontend
flyctl deploy --build-arg REACT_APP_API_URL=https://nowait-backend.fly.dev/api

# Alternatively, you can create a .env.production file with:
# REACT_APP_API_URL=https://nowait-backend.fly.dev/api
```

### 4. Configure Frontend Build with API URL

Create a `.env.production` file in the frontend directory:

```bash
echo "REACT_APP_API_URL=https://nowait-backend.fly.dev/api" > frontend/.env.production
```

Then deploy:
```bash
cd frontend
flyctl deploy
```

## Verify Deployment

### Backend
```bash
curl https://nowait-backend.fly.dev/
# Should return: {"message": "Welcome to Universal Queue System API"}
```

### Frontend
Visit https://nowait-frontend.fly.dev in your browser

## Useful Commands

### View logs
```bash
# Backend logs
cd backend && flyctl logs

# Frontend logs
cd frontend && flyctl logs
```

### Scale apps
```bash
# Scale backend
cd backend && flyctl scale vm shared-cpu-1x --memory 1024

# Scale frontend
cd frontend && flyctl scale vm shared-cpu-1x --memory 512
```

### Update secrets
```bash
cd backend
flyctl secrets set SECRET_KEY="new-secret-key"
```

### SSH into app
```bash
cd backend
flyctl ssh console
```

### Check app status
```bash
cd backend && flyctl status
cd frontend && flyctl status
```

## Cost Optimization

Fly.io offers a generous free tier:
- 3 shared-cpu-1x VMs with 256MB RAM each
- 3GB persistent storage
- 160GB outbound data transfer

Your configuration uses:
- Backend: 1 VM with 1GB RAM (may need paid plan)
- Frontend: 1 VM with 512MB RAM

To reduce costs:
- Set `min_machines_running = 0` in fly.toml (already configured)
- Machines will auto-stop when idle and auto-start on requests
- First request after sleep will be slower (cold start)

## Troubleshooting

### Build failures
```bash
# Check builder logs
flyctl logs --app nowait-backend

# Try deploying with verbose output
flyctl deploy --verbose
```

### Connection issues
- Ensure CORS is properly configured in backend
- Check that environment variables are set correctly
- Verify the frontend is using the correct backend URL

### Database connection issues
- Ensure Supabase credentials are correct
- Check that Supabase allows connections from Fly.io IPs

## Environment Variables Reference

### Backend
- `SECRET_KEY`: JWT token signing key
- `SUPABASE_URL`: Your Supabase project URL
- `SUPABASE_KEY`: Service role key
- `SUPABASE_ANON_KEY`: Anonymous key
- `EMAIL_HOST`: SMTP host
- `EMAIL_PORT`: SMTP port
- `EMAIL_USER`: Email address for sending
- `EMAIL_PASSWORD`: App-specific password
- `EMAIL_FROM`: From email address
- `FRONTEND_URL`: Frontend URL for email links

### Frontend
- `REACT_APP_API_URL`: Backend API URL (build-time variable)

## Next Steps

After deployment:
1. Test all features thoroughly
2. Set up custom domains (optional)
3. Configure monitoring and alerts
4. Set up CI/CD for automated deployments
5. Consider adding Redis for caching if needed
