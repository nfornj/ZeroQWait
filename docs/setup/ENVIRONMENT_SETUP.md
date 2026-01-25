# Environment Configuration Summary

## ✅ What's Been Configured

Your application now automatically works in both **local** and **production** environments!

## 📁 Environment Files Created

### Frontend (`frontend/`)
- **`.env.development`** → `http://localhost:8000/api` (for local dev)
- **`.env.production`** → `https://nowait-backend.fly.dev/api` (for production)
- **`.env.local`** → `http://localhost:8000/api` (local overrides, not committed)

### How It Works
React automatically picks the right `.env` file based on the command:
- `npm start` → uses `.env.development`
- `npm run build` → uses `.env.production`
- `.env.local` → always overrides (useful for testing)

## 🚀 Local Development

```bash
# Start everything
docker-compose up --build

# Or start individually
# Backend
cd backend && pdm run start

# Frontend (in another terminal)
cd frontend && npm start
```

**Frontend**: http://localhost:3000  
**Backend API**: http://localhost:8000  
**API Docs**: http://localhost:8000/docs

## 🌐 Production Deployment

### For Fly.io (or similar)

**Backend:**
```bash
cd backend
fly deploy
```

**Frontend:**
```bash
cd frontend
# .env.production already has the right URL
npm run build
fly deploy
```

### For Custom Domain

Update `frontend/.env.production`:
```
REACT_APP_API_URL=https://your-api-domain.com/api
```

Then build:
```bash
cd frontend
npm run build
# Deploy the 'build' folder
```

## 🔧 Configuration Files

### `docker-compose.yml`
```yaml
frontend:
  build:
    context: ./frontend
  environment:
    - REACT_APP_API_URL=http://localhost:8000/api  # Local dev
```

### `frontend/src/index.tsx`
```typescript
import axios from 'axios';

// Automatically uses the right API URL based on environment
axios.defaults.baseURL = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';
```

### `backend/main.py`
```python
allowed_origins = [
    "http://localhost:3000",        # Local frontend
    "https://nowait.fly.dev",       # Production frontend
]
```

## 🐛 Troubleshooting

### Login not working?
1. **Hard refresh**: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows)
2. **Check console**: DevTools → Network tab → Look at request URL
3. **Verify API URL**: Should be `http://localhost:8000/api/auth/token`

### Wrong API URL?
```bash
# Check which URL is compiled in the build
docker-compose exec frontend sh -c 'grep -o "localhost:8000\|nowait-backend" /usr/share/nginx/html/static/js/*.js | head -3'

# Should show: localhost:8000
```

### After changing environment files:
```bash
# Must rebuild for changes to take effect
docker-compose up --build frontend
```

## 📝 Adding a New Environment Variable

1. **Add to `.env.development` and `.env.production`**:
```
REACT_APP_NEW_VAR=value
```

2. **Use in code** (must start with `REACT_APP_`):
```typescript
const newVar = process.env.REACT_APP_NEW_VAR;
```

3. **Rebuild**:
```bash
docker-compose up --build frontend
```

## 🔐 Security Notes

- ✅ `.env.local` is in `.gitignore` (safe for local secrets)
- ✅ Production secrets should be set via your hosting platform
- ✅ Never commit API keys or passwords to git
- ✅ Backend uses CORS to restrict which domains can access it

## 📚 Full Documentation

See `DEPLOYMENT_GUIDE.md` for complete deployment instructions.

## Quick Test

### Verify Local Setup
```bash
# Terminal
curl http://localhost:8000/api/

# Should return: {"message":"Welcome to Universal Queue System API"}
```

### Verify Frontend API URL
```javascript
// Browser console (on http://localhost:3000)
console.log(process.env.REACT_APP_API_URL)
// Should show: http://localhost:8000/api
```

---

**✅ You're all set!** The application will automatically use the correct API URL for each environment.
