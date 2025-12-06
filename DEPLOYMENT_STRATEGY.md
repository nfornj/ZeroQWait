# ZeroQwait Deployment Strategy

## Overview

ZeroQwait has been migrated from Fly.io cloud hosting to self-hosting on a Raspberry Pi at home. This document outlines the deployment strategy and provides quick links to all relevant documentation.

## Current Status

- ✅ **Domain**: zeroqwait.com (active, pointing to home IP)
- ✅ **Frontend**: Accessible and serving correctly
- ⚠️ **Backend/API**: Needs Nginx reverse proxy configuration for login to work
- ✅ **Database**: Supabase (cloud-hosted, working)

## Why Self-Hosting on Raspberry Pi?

1. **Cost**: No monthly cloud hosting fees
2. **Control**: Full control over infrastructure
3. **Learning**: Hands-on experience with server management
4. **Privacy**: Data processing happens at home

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Internet                          │
└─────────────────┬───────────────────────────────────┘
                  │
                  │ zeroqwait.com
                  ↓
          ┌───────────────┐
          │  Home Router  │  Port forwarding (80, 443)
          └───────┬───────┘
                  │
                  ↓
     ┌────────────────────────────┐
     │    Raspberry Pi (Home)     │
     │                            │
     │  ┌──────────────────────┐ │
     │  │  Nginx (Port 80/443) │ │  ← SSL termination & reverse proxy
     │  └──────────┬───────────┘ │
     │             │              │
     │    ┌────────┴────────┐    │
     │    ↓                 ↓    │
     │  Frontend         Backend │
     │  (Docker:3000)   (Docker:8000) │
     │  React App       FastAPI   │
     │                             │
     └─────────────────────────────┘
                  │
                  ↓
          ┌──────────────┐
          │   Supabase   │  ← Cloud database
          │  (PostgreSQL)│
          └──────────────┘
```

## Documentation Index

All documentation has been reorganized for clarity:

### 🚀 Primary Documentation

1. **[PI_SETUP_CHECKLIST.md](PI_SETUP_CHECKLIST.md)** - Start here!
   - Quick checklist for deployment
   - Current status diagnostics
   - Common issues and solutions

2. **[RASPBERRY_PI_DEPLOYMENT.md](RASPBERRY_PI_DEPLOYMENT.md)** - Complete guide
   - Detailed deployment steps
   - Nginx configuration
   - SSL setup with Let's Encrypt
   - Monitoring and maintenance
   - Troubleshooting

3. **[README.md](README.md)** - Project overview
   - Features and tech stack
   - Local development setup
   - API documentation
   - Quick deployment command

### 🛠️ Development

4. **[WARP.md](WARP.md)** - Development guidelines
   - Project architecture
   - Development commands
   - Code patterns

### 📦 Archived (Old Fly.io Deployment)

Old Fly.io-related documentation has been moved to `docs/archive/`:
- `FLY_DEPLOYMENT.md`
- `DEPLOYMENT_*.md` (various Fly.io deployment guides)
- `fly.toml` files
- `deploy.sh` (Fly.io deployment script)
- `setup-flyio.sh`

## Quick Start

### From Your Local Machine

```bash
# 1. Deploy to Pi (transfers code and restarts containers)
./deploy-pi.sh

# 2. SSH into Pi to configure Nginx (first time only)
ssh pi@your-pi-address
# Follow steps in RASPBERRY_PI_DEPLOYMENT.md section 5
```

### On the Raspberry Pi

```bash
# Check status
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Restart services
docker-compose -f docker-compose.prod.yml restart

# Update from Git (if using)
git pull
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

## Current Issue: Login Not Working

### Problem

When trying to log in at https://zeroqwait.com, the API requests to `/api/auth/login` are returning the frontend HTML instead of JSON responses from the backend.

### Root Cause

The Nginx reverse proxy is either:
1. Not installed/configured on the Pi
2. Not routing `/api/*` requests to the backend on port 8000

### Solution

You need to configure Nginx on the Pi to act as a reverse proxy. The complete Nginx configuration is provided in **[RASPBERRY_PI_DEPLOYMENT.md](RASPBERRY_PI_DEPLOYMENT.md#5-configure-nginx-reverse-proxy)**.

Quick diagnosis on your Pi:

```bash
# Check if Nginx is running
sudo systemctl status nginx

# Check what's serving on port 80/443
sudo netstat -tlnp | grep -E ':(80|443)'

# Test backend directly
curl http://localhost:8000/

# Test API through public URL (this should return JSON, not HTML)
curl https://zeroqwait.com/api/
```

## Key Files

### Configuration Files

- `docker-compose.prod.yml` - Production Docker setup
- `backend/.env` - Backend environment variables (not in Git)
- `frontend/.env.production` - Frontend production config
- `backend/Dockerfile` - Backend container definition
- `frontend/Dockerfile` - Frontend container definition
- `frontend/nginx.conf` - Nginx config for frontend container

### Deployment Scripts

- `deploy-pi.sh` - Main deployment script (run from Mac)
- Auto-start systemd service (configured on Pi)

### Documentation

- `RASPBERRY_PI_DEPLOYMENT.md` - Complete deployment guide
- `PI_SETUP_CHECKLIST.md` - Quick setup checklist
- `README.md` - Project documentation
- `DEPLOYMENT_STRATEGY.md` - This file

## Network Requirements

### Router Configuration

Port forwarding must be set up on your home router:

| External Port | Internal IP | Internal Port | Protocol |
|---------------|-------------|---------------|----------|
| 80            | Pi IP       | 80            | TCP      |
| 443           | Pi IP       | 443           | TCP      |

### DNS Configuration

Domain: `zeroqwait.com`
- A record pointing to your home's public IP
- Consider using Dynamic DNS if you don't have a static IP

### Security Recommendations

1. **Firewall**: Configure UFW on Pi to only allow necessary ports
2. **SSH**: Use key-based authentication, disable password auth
3. **Updates**: Regular system and Docker image updates
4. **Monitoring**: Set up fail2ban for brute-force protection
5. **Backups**: Automated daily backups of code and configuration

## Environment Variables

### Required Backend Variables

```env
SUPABASE_URL=<your-supabase-url>
SUPABASE_KEY=<your-service-role-key>
SUPABASE_ANON_KEY=<your-anon-key>
SECRET_KEY=<jwt-secret-key>
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=<your-email>
EMAIL_PASSWORD=<your-app-password>
FRONTEND_URL=https://zeroqwait.com
```

### Frontend Build Argument

```env
REACT_APP_API_URL=/api
```

This is set in `docker-compose.prod.yml` as a build arg.

## Maintenance

### Regular Tasks

**Daily (Automated)**
- Docker health checks
- Log rotation
- Backups

**Weekly**
- Review logs for errors
- Check disk space
- Monitor system resources

**Monthly**
- System updates (`sudo apt-get update && sudo apt-get upgrade`)
- Docker image cleanup (`docker system prune`)
- SSL certificate check (auto-renewed by certbot)
- Test backup restoration

### Updating Code

```bash
# From your Mac
./deploy-pi.sh

# Or manually on the Pi
cd ~/zeroqwait
git pull  # If using Git
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

## Monitoring

### Check Service Health

```bash
# On the Pi
docker ps                              # Container status
docker stats                           # Resource usage
sudo systemctl status nginx            # Nginx status
sudo certbot certificates              # SSL certificate status
```

### View Logs

```bash
# Application logs
docker-compose -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.prod.yml logs -f frontend

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# System logs
journalctl -u zeroqwait.service -f
```

## Rollback Strategy

If something goes wrong:

1. **Rollback code**: Restore from backup or Git
2. **Restart containers**: 
   ```bash
   docker-compose -f docker-compose.prod.yml restart
   ```
3. **Rebuild from scratch**:
   ```bash
   docker-compose -f docker-compose.prod.yml down
   docker-compose -f docker-compose.prod.yml build --no-cache
   docker-compose -f docker-compose.prod.yml up -d
   ```
4. **Restore Nginx config**: Keep a backup of working config

## Performance Considerations

Raspberry Pi has limited resources compared to cloud hosting:

- **CPU**: ARM processor, slower than cloud VMs
- **RAM**: 1-8GB depending on Pi model
- **Network**: Limited by home internet upload speed
- **Storage**: SD card (slower than SSD)

### Optimizations

1. Use multi-stage Docker builds to reduce image size
2. Enable Docker health checks for auto-restart
3. Configure swap space for memory-intensive operations
4. Monitor Pi temperature (`vcgencmd measure_temp`)
5. Use Nginx caching for static assets
6. Consider CDN for frontend assets (optional)

## Future Improvements

- [ ] Set up monitoring dashboard (Prometheus + Grafana)
- [ ] Configure automated backups to cloud storage
- [ ] Set up log aggregation
- [ ] Implement CI/CD pipeline for automated deployments
- [ ] Add rate limiting in Nginx
- [ ] Set up alerting for service failures
- [ ] Configure Redis for caching (optional)
- [ ] Load testing and performance tuning

## Support and Resources

### Getting Help

1. Check `PI_SETUP_CHECKLIST.md` for common issues
2. Review logs (Docker and Nginx)
3. Test each component individually
4. Verify network connectivity and DNS

### Useful Commands Reference

```bash
# Docker
docker-compose -f docker-compose.prod.yml ps      # Status
docker-compose -f docker-compose.prod.yml logs    # Logs
docker-compose -f docker-compose.prod.yml restart # Restart
docker-compose -f docker-compose.prod.yml down    # Stop
docker-compose -f docker-compose.prod.yml up -d   # Start

# Nginx
sudo systemctl status nginx                        # Status
sudo systemctl restart nginx                       # Restart
sudo nginx -t                                      # Test config
sudo tail -f /var/log/nginx/error.log             # Logs

# System
htop                                               # System resources
df -h                                              # Disk space
vcgencmd measure_temp                              # Pi temperature
sudo systemctl status zeroqwait.service           # Auto-start service

# SSL
sudo certbot certificates                          # Check certificates
sudo certbot renew                                 # Renew certificates
```

## Changes from Fly.io

| Aspect | Fly.io (Old) | Raspberry Pi (New) |
|--------|--------------|-------------------|
| Hosting | Cloud | Self-hosted at home |
| Cost | ~$10-20/month | One-time Pi cost + electricity |
| Scalability | Auto-scaling | Manual (single Pi) |
| Deployment | `flyctl deploy` | `./deploy-pi.sh` |
| SSL | Automatic | Let's Encrypt (certbot) |
| Database | Fly Postgres | Supabase (cloud) |
| Load Balancing | Built-in | Single instance |
| Monitoring | Fly dashboard | Manual setup |
| Backups | Automated | Manual setup |

## Conclusion

The migration from Fly.io to self-hosting on Raspberry Pi provides cost savings and learning opportunities. While it requires more manual configuration and maintenance, the comprehensive documentation and deployment scripts make it manageable.

**Next Step**: Follow the `PI_SETUP_CHECKLIST.md` to complete the Nginx reverse proxy setup and fix the login issue.
