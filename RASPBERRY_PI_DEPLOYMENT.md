# Raspberry Pi Deployment Guide for ZeroQwait

This guide covers deploying ZeroQwait on a Raspberry Pi for self-hosting from home.

## Overview

Your Raspberry Pi will run:
- **Frontend**: React app served via Nginx on port 80/443
- **Backend**: FastAPI application on port 8000
- **Database**: Supabase (cloud-hosted, already configured)
- **Reverse Proxy**: Nginx to route requests between frontend and backend

## Prerequisites

- Raspberry Pi (3B+ or newer recommended) with Raspbian/Raspberry Pi OS
- Docker and Docker Compose installed on the Pi
- Domain name (zeroqwait.com) pointing to your home IP
- Port forwarding configured on your router (ports 80 and 443)
- Static IP or Dynamic DNS for your home network

## Architecture

```
Internet → Router:443 → Raspberry Pi:443 (Nginx)
                                        ↓
                              ┌─────────┴─────────┐
                              ↓                   ↓
                         Frontend           Backend:8000
                        (React/Nginx)       (FastAPI)
                                                ↓
                                           Supabase DB
```

## Deployment Steps

### 1. Prepare Your Raspberry Pi

SSH into your Raspberry Pi:

```bash
ssh pi@your-pi-address
```

Install Docker and Docker Compose if not already installed:

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo apt-get install -y docker-compose

# Verify installation
docker --version
docker-compose --version
```

### 2. Clone or Transfer Your Code

Transfer your code to the Pi:

```bash
# From your local machine
rsync -avz --exclude 'node_modules' --exclude '__pycache__' \
  /Users/neekrish/FastCuts/ pi@your-pi-address:~/zeroqwait/
```

Or clone from Git:

```bash
# On the Pi
cd ~
git clone <your-repo-url> zeroqwait
cd zeroqwait
```

### 3. Environment Configuration

Create/update the backend `.env` file on the Pi:

```bash
cd ~/zeroqwait/backend
nano .env
```

Ensure it contains:

```env
# Supabase Configuration
SUPABASE_URL=https://yuxfpspyzyhesfuspjns.supabase.co
SUPABASE_KEY=<your-service-role-key>
SUPABASE_ANON_KEY=<your-anon-key>

# JWT Secret Key
SECRET_KEY=09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7

# Email Configuration
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USER=nfornj@gmail.com
EMAIL_PASSWORD=<your-app-password>
EMAIL_FROM=nfornj@gmail.com
FRONTEND_URL=https://zeroqwait.com
```

### 4. Build and Start Services

```bash
cd ~/zeroqwait

# Build the Docker images
docker-compose -f docker-compose.prod.yml build

# Start services in detached mode
docker-compose -f docker-compose.prod.yml up -d
```

### 5. Configure Nginx Reverse Proxy

On the Pi, install Nginx (outside Docker) to handle SSL and routing:

```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

Create Nginx configuration:

```bash
sudo nano /etc/nginx/sites-available/zeroqwait
```

Add the following configuration:

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name zeroqwait.com www.zeroqwait.com;
    
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name zeroqwait.com www.zeroqwait.com;

    # SSL certificates (will be configured by certbot)
    ssl_certificate /etc/letsencrypt/live/zeroqwait.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/zeroqwait.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Increase buffer sizes for larger requests
    client_max_body_size 10M;
    client_body_buffer_size 128k;

    # Backend API proxy
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 90;
    }

    # Backend docs
    location /docs {
        proxy_pass http://localhost:8000/docs;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Backend OpenAPI
    location /openapi.json {
        proxy_pass http://localhost:8000/openapi.json;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # Static uploads
    location /static/ {
        proxy_pass http://localhost:8000/static/;
        proxy_http_version 1.1;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Frontend (React app)
    location / {
        proxy_pass http://localhost:3000/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        
        # Handle React Router
        proxy_intercept_errors on;
        error_page 404 = @frontend;
    }

    location @frontend {
        proxy_pass http://localhost:3000/;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/zeroqwait /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # Remove default site
sudo nginx -t  # Test configuration
sudo systemctl restart nginx
```

### 6. SSL Certificate Setup

Get a free SSL certificate from Let's Encrypt:

```bash
sudo certbot --nginx -d zeroqwait.com -d www.zeroqwait.com
```

Follow the prompts and choose to redirect HTTP to HTTPS.

Certbot will automatically:
- Obtain the SSL certificate
- Update your Nginx config with SSL settings
- Set up auto-renewal

Test auto-renewal:

```bash
sudo certbot renew --dry-run
```

### 7. Verify Deployment

Check that all services are running:

```bash
# Check Docker containers
docker-compose -f docker-compose.prod.yml ps

# Check logs
docker-compose -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.prod.yml logs -f frontend

# Check Nginx
sudo systemctl status nginx
```

Test the endpoints:

```bash
# API health check
curl http://localhost:8000/

# Frontend health check  
curl http://localhost:3000/

# External access
curl https://zeroqwait.com/api/
```

## Maintenance Commands

### View Logs

```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.prod.yml logs -f frontend

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

### Update Deployment

```bash
cd ~/zeroqwait

# Pull latest changes (if using Git)
git pull

# Rebuild and restart
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# Restart Nginx if config changed
sudo systemctl restart nginx
```

### Restart Services

```bash
# Restart all containers
docker-compose -f docker-compose.prod.yml restart

# Restart specific service
docker-compose -f docker-compose.prod.yml restart backend
docker-compose -f docker-compose.prod.yml restart frontend

# Restart Nginx
sudo systemctl restart nginx
```

### Monitor System Resources

```bash
# Docker stats
docker stats

# System resources
htop

# Disk usage
df -h
docker system df
```

### Clean Up

```bash
# Remove old images
docker image prune -a

# Remove old containers
docker container prune

# Full cleanup (careful!)
docker system prune -a --volumes
```

## Auto-Start on Boot

Ensure Docker Compose starts on boot:

```bash
# Create systemd service
sudo nano /etc/systemd/system/zeroqwait.service
```

Add:

```ini
[Unit]
Description=ZeroQwait Docker Compose Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/pi/zeroqwait
ExecStart=/usr/bin/docker-compose -f docker-compose.prod.yml up -d
ExecStop=/usr/bin/docker-compose -f docker-compose.prod.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl enable zeroqwait.service
sudo systemctl start zeroqwait.service
sudo systemctl status zeroqwait.service
```

## Troubleshooting

### Login Not Working

1. **Check CORS settings**: Ensure backend allows `https://zeroqwait.com`
   ```bash
   docker-compose -f docker-compose.prod.yml logs backend | grep CORS
   ```

2. **Check API routing**: Test backend directly
   ```bash
   curl http://localhost:8000/api/auth/login -X POST \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","password":"test"}'
   ```

3. **Check Nginx proxy**: Look for proxy errors
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```

4. **Verify environment variables**:
   ```bash
   docker-compose -f docker-compose.prod.yml exec backend env | grep SECRET_KEY
   ```

### Container Not Starting

```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs

# Check container status
docker ps -a

# Rebuild from scratch
docker-compose -f docker-compose.prod.yml down -v
docker-compose -f docker-compose.prod.yml build --no-cache
docker-compose -f docker-compose.prod.yml up -d
```

### SSL Certificate Issues

```bash
# Check certificate status
sudo certbot certificates

# Renew certificate manually
sudo certbot renew --force-renewal

# Test Nginx SSL config
sudo nginx -t
```

### Performance Issues

On Raspberry Pi, consider:

1. **Reduce build parallelism**: Edit Dockerfiles to use fewer build threads
2. **Increase swap space**:
   ```bash
   sudo dphys-swapfile swapoff
   sudo nano /etc/dphys-swapfile  # Set CONF_SWAPSIZE=2048
   sudo dphys-swapfile setup
   sudo dphys-swapfile swapon
   ```
3. **Monitor temperature**: 
   ```bash
   vcgencmd measure_temp
   ```

## Network Configuration

### Router Port Forwarding

Forward these ports from your router to your Pi's local IP:
- Port 80 (HTTP) → Pi:80
- Port 443 (HTTPS) → Pi:443

### Dynamic DNS (Optional)

If you don't have a static IP, use a DDNS service:

```bash
# Example with ddclient
sudo apt-get install ddclient
sudo nano /etc/ddclient.conf
```

### Firewall

```bash
# Allow only necessary ports
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable
```

## Backup Strategy

### Automated Backups

Create a backup script:

```bash
nano ~/backup-zeroqwait.sh
```

Add:

```bash
#!/bin/bash
BACKUP_DIR="/home/pi/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Backup code
tar -czf $BACKUP_DIR/zeroqwait-code-$DATE.tar.gz -C /home/pi zeroqwait

# Backup environment files
cp /home/pi/zeroqwait/backend/.env $BACKUP_DIR/.env-$DATE

# Keep only last 7 backups
find $BACKUP_DIR -name "zeroqwait-code-*.tar.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
```

Make executable and schedule:

```bash
chmod +x ~/backup-zeroqwait.sh

# Add to crontab (daily at 2 AM)
crontab -e
# Add: 0 2 * * * /home/pi/backup-zeroqwait.sh >> /home/pi/backup.log 2>&1
```

## Security Recommendations

1. **Change default Pi password**
2. **Use SSH keys instead of passwords**
3. **Keep system updated**:
   ```bash
   sudo apt-get update && sudo apt-get upgrade -y
   ```
4. **Install fail2ban**:
   ```bash
   sudo apt-get install fail2ban
   ```
5. **Regular security audits**:
   ```bash
   docker scan <image-name>
   ```
6. **Use secrets management**: Consider using Docker secrets or environment-specific .env files

## Monitoring Setup (Optional)

Install monitoring tools:

```bash
# Prometheus + Grafana
docker run -d -p 9090:9090 prom/prometheus
docker run -d -p 3001:3000 grafana/grafana
```

## Quick Reference

| Service | Internal Port | External URL |
|---------|--------------|--------------|
| Frontend | 3000 | https://zeroqwait.com |
| Backend | 8000 | https://zeroqwait.com/api |
| API Docs | 8000 | https://zeroqwait.com/docs |
| Nginx | 80/443 | Entry point |

## Support

For issues or questions:
1. Check logs first
2. Review Nginx error logs
3. Test API endpoints directly
4. Verify environment variables
5. Check Supabase connectivity

## Next Steps After Deployment

1. Test all functionality (registration, login, queues)
2. Set up monitoring and alerts
3. Configure automated backups
4. Document any custom configurations
5. Test disaster recovery procedures
