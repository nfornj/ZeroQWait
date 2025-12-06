# Deployment Guide - Environment Configuration

This guide explains how to configure the application for different environments.

## Environment Files

The application uses different `.env` files for different environments:

- **`.env.development`** - Used during local development (`npm start`)
- **`.env.production`** - Used for production builds (`npm run build`)
- **`.env.local`** - Local overrides (not committed to git)

## Local Development

### Using Docker Compose (Recommended)

```bash
docker-compose up --build
```

The frontend will automatically use `http://localhost:8000/api` as configured in:
- `frontend/.env.development` (for development)
- `frontend/.env.local` (for local overrides)
- `docker-compose.yml` environment variables

### Using npm (Alternative)

```bash
# Start backend
cd backend
pdm run start

# Start frontend (in another terminal)
cd frontend
npm start
```

The frontend will use `REACT_APP_API_URL=http://localhost:8000/api` from `.env.development`.

## Production Deployment

### Option 1: Using Docker (Recommended)

Build with production API URL:

```bash
# Build frontend with production API URL
docker build \
  --build-arg REACT_APP_API_URL=https://your-backend-domain.com/api \
  -t your-app-frontend \
  ./frontend

# Build backend
docker build -t your-app-backend ./backend
```

### Option 2: Using Fly.io

**Backend (fly.io):**
```bash
cd backend
fly deploy
```

**Frontend (fly.io):**

Update `frontend/.env.production` with your backend URL:
```
REACT_APP_API_URL=https://your-backend.fly.dev/api
```

Then deploy:
```bash
cd frontend
npm run build
fly deploy
```

### Option 3: Manual Build

```bash
cd frontend

# Set the production API URL
export REACT_APP_API_URL=https://your-backend-domain.com/api

# Build
npm run build

# The build folder contains static files ready to deploy
```

## Environment Variables

### Frontend

| Variable | Development | Production |
|----------|------------|------------|
| `REACT_APP_API_URL` | `http://localhost:8000/api` | `https://your-backend.fly.dev/api` |

### Backend

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SECRET_KEY` | Yes | JWT signing key |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_KEY` | Yes | Supabase service role key |
| `FRONTEND_URL` | No | CORS allowed origin (optional) |
| `SMTP_SERVER` | Yes* | Email server (for password reset) |
| `SMTP_PORT` | Yes* | Email server port |
| `SMTP_USERNAME` | Yes* | Email username |
| `SMTP_PASSWORD` | Yes* | Email password |
| `FROM_EMAIL` | Yes* | Sender email address |

*Required for password reset functionality

## CORS Configuration

The backend (`backend/main.py`) is configured to allow requests from:
- `http://localhost:3000` (local development)
- `https://nowait.fly.dev` (production frontend)
- Any URL set in `FRONTEND_URL` environment variable

To add a new frontend URL:

```python
# backend/main.py
allowed_origins = [
    "http://localhost:3000",
    "https://nowait.fly.dev",
    "https://your-custom-domain.com",  # Add your domain here
]
```

## Verifying Configuration

### Check Frontend API URL

Open browser console and run:
```javascript
console.log(process.env.REACT_APP_API_URL)
```

Or check the compiled JavaScript files:
```bash
grep -o "localhost:8000\|your-backend-domain" frontend/build/static/js/*.js | head -3
```

### Test API Connection

```bash
# From browser console (when app is running)
fetch('/auth/token')
  .then(r => console.log('API URL:', r.url))
```

### Check Backend CORS

```bash
curl -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: content-type" \
     -X OPTIONS \
     http://localhost:8000/api/auth/token
```

Should return `200 OK` with CORS headers.

## Common Issues

### "Login failed" or 405 errors
- **Cause**: Frontend is using wrong API URL
- **Fix**: Check `.env.local` or rebuild with correct `REACT_APP_API_URL`
- **Verify**: Check browser DevTools → Network tab → Request URL

### CORS errors
- **Cause**: Backend doesn't allow requests from your frontend domain
- **Fix**: Add your domain to `allowed_origins` in `backend/main.py`
- **Verify**: Check preflight OPTIONS request

### Environment variables not updating
- **Cause**: React only reads env vars at build time
- **Fix**: Rebuild the frontend after changing `.env` files
```bash
docker-compose up --build frontend
# or
npm run build
```

## Quick Reference

| Environment | Frontend URL | Backend URL | Build Command |
|------------|--------------|-------------|---------------|
| Local Dev | `http://localhost:3000` | `http://localhost:8000` | `docker-compose up` |
| Production | `https://nowait.fly.dev` | `https://nowait-backend.fly.dev` | `npm run build` |

## Security Notes

1. **Never commit** `.env.local` to git (already in `.gitignore`)
2. **Never commit** production secrets to git
3. Use environment variables or secrets management for production
4. Rotate `SECRET_KEY` regularly
5. Use HTTPS in production (required for OAuth, cookies, etc.)
