# ZeroQwait Deployment Guide with Subdomain Support

## Overview

This guide covers deploying ZeroQwait with shop-based subdomains enabled. The system supports multi-shop environments where each shop is accessible via its own subdomain:

- Base: `http://192.168.2.88.nip.io`
- Shop 1: `http://pizza-palace.192.168.2.88.nip.io`
- Shop 2: `http://coffee-shop.192.168.2.88.nip.io`

## Prerequisites

- Docker & Docker Compose (for local deployment)
- OR Kubernetes cluster with Traefik (for K8s deployment)
- nip.io DNS (automatic, no setup needed)
- 192.168.2.88 IP reachable from your browser

## Recent Updates to Your Code

### 1. Frontend Login Redirect

**File**: `frontend/src/pages/LoginPage.tsx`

- After login, users are automatically redirected to their shop's subdomain
- Uses shop slug from backend to construct the URL
- Handles nip.io, localhost, and custom domains

### 2. Backend CORS Configuration

**File**: `backend/main.py`

- Added wildcard support for all shop subdomains
- Frontend can make API calls across subdomains

### 3. Database Models

**File**: `backend/models.py`

- Shop model includes `slug` field (unique, indexed)
- Used for URL-friendly shop identification

### 4. Docker Compose

**File**: `docker-compose.yml`

- Updated to use `/api` relative path for frontend API calls
- FRONTEND_URL set to `http://192.168.2.88.nip.io`

### 5. Kubernetes ConfigMap

**File**: `k8s-manifests/backend-configmap.yaml`

- Updated FRONTEND_URL to `http://192.168.2.88.nip.io`
- Removed hardcoded NodePort references

### 6. Kubernetes Frontend Deployment

**File**: `k8s-manifests/frontend-deployment.yaml`

- Frontend built with relative API URL `/api`
- Works with Traefik ingress routing

## Deployment Methods

### Method 1: Local Docker (Recommended for Testing)

```bash
./deploy-local.sh
```

**What it does:**

1. Stops old containers
2. Builds fresh images
3. Starts backend and frontend
4. Waits for services to be healthy

**Access:**

- Homepage: `http://192.168.2.88.nip.io:3000`
- Backend API: `http://192.168.2.88.nip.io:8000`
- Swagger UI: `http://192.168.2.88.nip.io:8000/docs`

**Key Differences from K8s:**

- Runs on your local machine
- Direct port access (3000, 8000)
- No ingress controller needed

### Method 2: Kubernetes Deployment

```bash
./deploy-k8s.sh
```

**What it does:**

1. Creates namespace
2. Sets up secrets and ConfigMaps
3. Deploys PostgreSQL
4. Deploys backend and frontend
5. Configures Traefik Ingress

**Access:**

- Homepage: `http://192.168.2.88.nip.io`
- Backend API: `http://192.168.2.88.nip.io/api`
- Swagger UI: `http://192.168.2.88.nip.io/api/docs`

**Requirements:**

- Kubernetes cluster running
- Traefik ingress controller installed
- Sufficient CPU/memory for containers

## How Subdomains Work

### User Flow

```
1. User visits: http://192.168.2.88.nip.io/login
                          ↓
2. User logs in with shop owner credentials
                          ↓
3. Frontend fetches user's shops via /api/shops/my-shops
                          ↓
4. Extracts shop slug (e.g., "pizza-palace")
                          ↓
5. Redirects to: http://pizza-palace.192.168.2.88.nip.io/dashboard
                          ↓
6. Ingress/Docker routes to same frontend:3000
                          ↓
7. Frontend makes API calls to /api (same host)
                          ↓
8. Backend receives request with Host header
                          ↓
9. Backend identifies user from JWT token
                          ↓
10. Returns user's shop-specific data
```

### Shop Identification

**Current Implementation (Token-based):**

- Backend identifies user from JWT token
- User's shops are queried from database
- All data is filtered by `owner_id`

**Optional Enhancement (Host-based):**

- Backend could read `Host` header
- Extract shop slug from subdomain
- Automatically scope queries to that shop

## Testing Checklist

### Before Deployment

- [ ] Check `.env` file has correct credentials
- [ ] Verify backend `.env` is not in git
- [ ] Database migrations are up to date
- [ ] Frontend build completes without errors
- [ ] All docker images build successfully

### After Deployment (Local Docker)

```bash
# Check containers are running
docker-compose ps

# View logs
docker-compose logs -f

# Test backend
curl http://192.168.2.88.nip.io:8000/

# Test frontend
curl http://192.168.2.88.nip.io:3000/
```

### After Deployment (K8s)

```bash
# Check pods
kubectl get pods -n zeroqwait

# Check ingress
kubectl get ingress -n zeroqwait

# View logs
kubectl logs -n zeroqwait -l app=backend -f
kubectl logs -n zeroqwait -l app=frontend -f

# Test endpoints
curl http://192.168.2.88.nip.io/
curl http://192.168.2.88.nip.io/api/
```

## Troubleshooting

### Issue: Cannot reach http://192.168.2.88.nip.io

**Solution:**

- Verify your machine's IP is 192.168.2.88
- Or update the IP in docker-compose.yml and K8s configs
- Verify DNS resolution: `ping 192.168.2.88.nip.io`

### Issue: Frontend displays but API calls fail

**Possible causes:**

- Backend CORS not configured for subdomain
- API URL in frontend not set correctly
- Backend service not accessible from frontend

**Check:**

```bash
# Check CORS headers
curl -H "Origin: http://pizza-palace.192.168.2.88.nip.io" http://192.168.2.88.nip.io/api/

# Check backend logs for errors
docker-compose logs backend
```

### Issue: Login redirect not working

**Possible causes:**

- Shop slug not being generated
- Frontend can't fetch `/api/shops/my-shops`
- localStorage token not set

**Check:**

```bash
# Verify shop has slug
curl http://192.168.2.88.nip.io:8000/api/shops/my-shops \
  -H "Authorization: Bearer $TOKEN"

# Check browser console for errors
# Check LocalStorage for token
```

### Issue: K8s pods not starting

**Troubleshoot:**

```bash
# Check pod status and events
kubectl describe pod <pod-name> -n zeroqwait

# Check logs
kubectl logs <pod-name> -n zeroqwait

# Check resource availability
kubectl top nodes
kubectl top pods -n zeroqwait

# Check ingress routing
kubectl describe ingress zeroqwait-ingress -n zeroqwait
```

## Environment Variables

### Backend (.env)

```env
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=fastcuts_db
DB_USER=postgres
DB_PASSWORD=your_password

# JWT
SECRET_KEY=your_secret_key_here

# Frontend URL (for CORS and email links)
FRONTEND_URL=http://192.168.2.88.nip.io

# Optional: Supabase (if using cloud DB)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_key_here
```

### Frontend (.env)

```env
REACT_APP_API_URL=/api
```

## Security Considerations

⚠️ **Important for Production:**

1. **Use HTTPS**
   - Replace nip.io with real domain
   - Obtain SSL certificates
   - Update FRONTEND_URL to https://

2. **Update CORS Origins**
   - Don't use wildcard `*` for production
   - Explicitly list allowed origins
   - Remove localhost from production

3. **Secrets Management**
   - Use proper secret management (not .env files)
   - Rotate keys regularly
   - Use strong JWT secret

4. **Database**
   - Use managed PostgreSQL (not local container)
   - Regular backups
   - Strong passwords

## Performance Tuning

### Local Docker

- Limit resource usage in docker-compose
- Use `.dockerignore` to reduce image size
- Mount volumes for hot reload during development

### Kubernetes

- Set resource requests and limits
- Configure horizontal pod autoscaling (HPA)
- Use node affinity for specific workloads

## Next Steps

1. **Test locally first:**

   ```bash
   ./deploy-local.sh
   ```

2. **Create test shop:**
   - Register as shop owner
   - Create a shop (slug auto-generated)
   - Login and verify redirect

3. **Test subdomains:**
   - Visit `shopname.192.168.2.88.nip.io`
   - Verify data is shop-specific

4. **Deploy to K8s:**
   ```bash
   ./deploy-k8s.sh
   ```

## Support

For issues or questions:

- Check logs: `docker-compose logs` or `kubectl logs`
- Review this guide's troubleshooting section
- Check ingress rules: `kubectl describe ingress`

---

**Last Updated:** January 18, 2026  
**Deployment Scripts:** deploy-local.sh, deploy-k8s.sh  
**Status:** Ready for testing
