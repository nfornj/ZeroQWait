# Quick Start: Deploy & Test Subdomains

## 30-Second Setup

```bash
cd /Users/neekrish/zeroqwait
./deploy-local.sh
```

## Testing (5 minutes)

1. **Open browser:**

   ```
   http://192.168.2.88.nip.io:3000
   ```

2. **Register as Shop Owner:**
   - Click "Sign Up"
   - Choose "Shop Owner"
   - Fill in details
   - Create account

3. **Create a Shop:**
   - After login, create new shop (e.g., "Pizza Palace")
   - Shop slug auto-generated: `pizza-palace`

4. **Logout & Login:**
   - Logout
   - Login again
   - Should redirect to: `http://pizza-palace.192.168.2.88.nip.io`

## Verify Deployment

```bash
# Check containers running
docker-compose ps

# View logs
docker-compose logs -f

# Test API
curl http://192.168.2.88.nip.io:8000/docs
```

## What Changed?

✅ **Frontend** - Redirects to shop subdomain after login  
✅ **Backend** - Supports all shop subdomains via CORS  
✅ **Docker** - Updated with correct nip.io URLs  
✅ **Kubernetes** - Ingress configured for wildcard subdomains

## Troubleshooting

| Issue                           | Solution                                                   |
| ------------------------------- | ---------------------------------------------------------- |
| Can't reach 192.168.2.88.nip.io | Update IP in scripts to your actual IP                     |
| API calls fail from subdomain   | Check backend logs: `docker-compose logs backend`          |
| Redirect not working            | Ensure you have a shop created before login                |
| DB errors                       | Check PostgreSQL container: `docker-compose logs postgres` |

## Next: Deploy to K8s

```bash
./deploy-k8s.sh
```

---

**Status:** Ready to test! 🚀
