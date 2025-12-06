# Raspberry Pi Setup Checklist

Quick checklist to get ZeroQwait running on your Raspberry Pi.

## ✅ Pre-Deployment Checklist

### Network Setup
- [ ] Domain (zeroqwait.com) points to your home IP address
- [ ] Router port forwarding configured:
  - Port 80 (HTTP) → Pi IP:80
  - Port 443 (HTTPS) → Pi IP:443
- [ ] Pi has static local IP or DHCP reservation
- [ ] Pi is accessible via SSH from your local machine

### Pi Configuration
- [ ] Raspberry Pi OS installed and updated
- [ ] SSH enabled
- [ ] Docker installed
- [ ] Docker Compose installed
- [ ] Sufficient storage space (at least 10GB free)
- [ ] Git installed (optional, for updates)

### Code and Environment
- [ ] Code transferred to Pi (in `~/zeroqwait`)
- [ ] Backend `.env` file configured with:
  - [ ] SUPABASE_URL
  - [ ] SUPABASE_KEY
  - [ ] SUPABASE_ANON_KEY
  - [ ] SECRET_KEY
  - [ ] EMAIL credentials
  - [ ] FRONTEND_URL=https://zeroqwait.com

## 🚀 Deployment Steps

### 1. Transfer Code
```bash
# From your Mac
./deploy-pi.sh
# Or manually:
rsync -avz --exclude 'node_modules' --exclude '__pycache__' \
  ./ pi@your-pi-address:~/zeroqwait/
```

### 2. Configure Environment
```bash
# On the Pi
ssh pi@your-pi-address
cd ~/zeroqwait/backend
nano .env  # Verify all settings
```

### 3. Build and Start Containers
```bash
cd ~/zeroqwait
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

### 4. Install and Configure Nginx
```bash
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx

# Create Nginx config (see RASPBERRY_PI_DEPLOYMENT.md for full config)
sudo nano /etc/nginx/sites-available/zeroqwait

# Enable site
sudo ln -s /etc/nginx/sites-available/zeroqwait /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

### 5. Get SSL Certificate
```bash
sudo certbot --nginx -d zeroqwait.com -d www.zeroqwait.com
```

### 6. Enable Auto-Start
```bash
# Create systemd service
sudo nano /etc/systemd/system/zeroqwait.service
# (See RASPBERRY_PI_DEPLOYMENT.md for service file content)

sudo systemctl enable zeroqwait.service
sudo systemctl start zeroqwait.service
```

## 🔍 Verification

### Test Internal Services
```bash
# On the Pi
curl http://localhost:8000/          # Backend health check
curl http://localhost:3000/          # Frontend
```

### Test External Access
```bash
# From your Mac or any device
curl https://zeroqwait.com/api/     # Should return JSON, not HTML
```

### Check Logs
```bash
# Docker logs
docker-compose -f docker-compose.prod.yml logs -f

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

## 🔧 Troubleshooting Current Login Issue

The login issue is likely because the Nginx reverse proxy is not configured. Here's what's happening:

1. ✅ Frontend is accessible at https://zeroqwait.com
2. ❌ API requests to `/api/*` are returning frontend HTML instead of backend JSON
3. 🔧 Solution: Configure Nginx to proxy `/api/*` requests to backend:8000

### Quick Fix

SSH into your Pi and check:

```bash
# Check if Nginx is installed
which nginx

# If not, install it
sudo apt-get install -y nginx

# Check what's currently serving on port 80/443
sudo netstat -tlnp | grep -E ':(80|443)'

# Check if backend is running
docker ps
curl http://localhost:8000/
```

Most likely scenario: You need to set up Nginx as described in step 4 above.

## 📊 Current Status Check

Run these commands on your Pi to check current status:

```bash
# Docker containers
docker ps -a

# Port bindings
sudo netstat -tlnp | grep -E ':(80|443|3000|8000)'

# Test backend directly
curl http://localhost:8000/

# Test API through public URL
curl https://zeroqwait.com/api/
```

## 🎯 Common Issues & Solutions

### Issue: Login returns HTML instead of JSON
**Cause**: Nginx not configured or not routing API requests correctly
**Solution**: Set up Nginx reverse proxy as described in RASPBERRY_PI_DEPLOYMENT.md

### Issue: SSL certificate errors
**Cause**: Certificate not obtained or expired
**Solution**: Run `sudo certbot --nginx -d zeroqwait.com -d www.zeroqwait.com`

### Issue: Backend not starting
**Cause**: Environment variables missing or incorrect
**Solution**: Check `backend/.env` file and container logs

### Issue: Port already in use
**Cause**: Another service using port 80 or 443
**Solution**: 
```bash
sudo systemctl stop apache2  # If Apache is running
sudo netstat -tlnp | grep :80  # Find what's using port 80
```

### Issue: Can't access from outside network
**Cause**: Port forwarding not configured
**Solution**: Configure router to forward ports 80 and 443 to Pi's IP

## 📝 Post-Deployment Tasks

- [ ] Test user registration
- [ ] Test user login
- [ ] Test creating a shop
- [ ] Test queue functionality
- [ ] Set up monitoring
- [ ] Configure automated backups
- [ ] Document any custom configurations
- [ ] Test SSL certificate auto-renewal

## 🔄 Regular Maintenance

### Weekly
- Check logs for errors
- Monitor disk space
- Verify SSL certificate status

### Monthly
- Update system packages
- Review and clean old Docker images
- Test backup restoration
- Review security logs

### As Needed
- Deploy code updates using `./deploy-pi.sh`
- Restart services if issues occur
- Review and optimize performance

## 📚 Additional Resources

- Full deployment guide: [RASPBERRY_PI_DEPLOYMENT.md](RASPBERRY_PI_DEPLOYMENT.md)
- Project documentation: [README.md](README.md)
- Development guide: [WARP.md](WARP.md)

## 🆘 Getting Help

If you encounter issues:

1. Check logs first (Docker and Nginx)
2. Verify all services are running
3. Test each component individually
4. Review the full deployment guide
5. Check network connectivity and DNS
