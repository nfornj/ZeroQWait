# GitHub Deployment Setup for ZeroQwait

This guide explains how to set up GitHub-based deployment for your ZeroQwait application.

## 📍 Current Setup

- **Local Development**: `/Users/neekrish/FastCuts/` (Your Mac)
- **Production Server**: `/home/pi/Documents/projects/apps/zeroqwait/` (Raspberry Pi)
- **Live Site**: https://zeroqwait.com

## 🎯 Deployment Workflow

```
Local Mac → GitHub → Raspberry Pi → Live Site
     ↓         ↓           ↓            ↓
  Develop    Push       Pull        Docker
   & Test   Changes   Changes      Rebuild
```

## 📋 One-Time Setup

### 1. Create GitHub Repository

If you haven't already:

```bash
# On your Mac
cd /Users/neekrish/FastCuts

# Initialize git (if not already done)
git init

# Add all files
git add .

# First commit
git commit -m "Initial commit - ZeroQwait application"

# Create repository on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/zeroqwait.git
git branch -M main
git push -u origin main
```

### 2. Set Up Git on Raspberry Pi

```bash
# SSH into your Pi
ssh pi@192.168.29.220

# Navigate to project directory
cd /home/pi/Documents/projects/apps/zeroqwait

# Initialize git and connect to GitHub
git init
git remote add origin https://github.com/YOUR_USERNAME/zeroqwait.git
git fetch
git checkout main

# Set up Git credentials (so you don't need password each time)
git config credential.helper store
```

### 3. Generate GitHub Personal Access Token (PAT)

Since GitHub no longer accepts passwords for Git operations:

1. Go to https://github.com/settings/tokens
2. Click **Generate new token** → **Generate new token (classic)**
3. Give it a name: "ZeroQwait Pi Deployment"
4. Select scopes:
   - ✅ `repo` (Full control of private repositories)
5. Click **Generate token**
6. **Copy the token** (you won't see it again!)
7. On the Pi, when you first `git pull`, use:
   - Username: your GitHub username
   - Password: paste the token

## 🚀 Daily Deployment Workflow

### Method 1: Automated Script (Recommended)

```bash
# On your Mac
cd /Users/neekrish/FastCuts
./deploy-github.sh
```

This script will:
1. Commit and push your changes to GitHub
2. SSH into Pi
3. Pull latest changes
4. Rebuild Docker containers
5. Restart services

### Method 2: Manual Deployment

```bash
# 1. On your Mac - Push changes
cd /Users/neekrish/FastCuts
git add .
git commit -m "Your commit message"
git push origin main

# 2. On Raspberry Pi - Pull and deploy
ssh pi@192.168.29.220
cd /home/pi/Documents/projects/apps/zeroqwait
git pull origin main
docker compose -f docker-compose.prod.simple.yml down
docker compose -f docker-compose.prod.simple.yml build
docker compose -f docker-compose.prod.simple.yml up -d
```

### Method 3: Quick Update (No Rebuild)

If you only changed frontend or backend code without dependencies:

```bash
ssh pi@192.168.29.220
cd /home/pi/Documents/projects/apps/zeroqwait
git pull origin main
docker compose -f docker-compose.prod.simple.yml restart
```

## 📁 .gitignore Configuration

Make sure your `.gitignore` includes:

```gitignore
# Environment variables
.env
.env.local
.env.production
*.env

# Dependencies
node_modules/
__pycache__/
*.pyc

# Build files
build/
dist/
*.egg-info/

# Logs
*.log
npm-debug.log*

# System files
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/

# Docker volumes
postgres_data/

# Archived files
docs/archive/
```

## 🔒 Security Best Practices

### Environment Variables

**Never commit sensitive data to GitHub!**

Your `.env` files should contain:
- API keys
- Database credentials
- Secret keys
- Email passwords

These must be manually configured on the Pi and never pushed to GitHub.

### On Raspberry Pi:

Ensure `/home/pi/Documents/projects/apps/zeroqwait/backend/.env` exists with:

```env
SUPABASE_URL=your_url
SUPABASE_KEY=your_key
SECRET_KEY=your_secret
EMAIL_PASSWORD=your_password
FRONTEND_URL=https://zeroqwait.com
```

## 🔄 Rollback Strategy

If deployment breaks something:

```bash
# On Pi
cd /home/pi/Documents/projects/apps/zeroqwait

# See recent commits
git log --oneline -5

# Rollback to previous commit
git reset --hard <commit-hash>

# Rebuild and restart
docker compose -f docker-compose.prod.simple.yml down
docker compose -f docker-compose.prod.simple.yml build
docker compose -f docker-compose.prod.simple.yml up -d
```

## 🐛 Troubleshooting

### Git Authentication Failed

```bash
# On Pi, re-enter credentials
git config --global credential.helper store
git pull  # Enter username and PAT when prompted
```

### Permission Denied

```bash
# Fix ownership
sudo chown -R pi:pi /home/pi/Documents/projects/apps/zeroqwait
```

### Docker Build Fails

```bash
# Clean rebuild
docker compose -f docker-compose.prod.simple.yml down -v
docker system prune -a
docker compose -f docker-compose.prod.simple.yml build --no-cache
docker compose -f docker-compose.prod.simple.yml up -d
```

### Site Not Loading After Deployment

```bash
# Check containers
docker compose -f docker-compose.prod.simple.yml ps

# Check logs
docker compose -f docker-compose.prod.simple.yml logs -f

# Restart cloudflared tunnel
sudo systemctl restart cloudflared
```

## 📊 Monitoring

### Check Application Status

```bash
# On Pi
cd /home/pi/Documents/projects/apps/zeroqwait

# Container status
docker compose -f docker-compose.prod.simple.yml ps

# Logs (all services)
docker compose -f docker-compose.prod.simple.yml logs -f

# Logs (specific service)
docker compose -f docker-compose.prod.simple.yml logs -f backend
docker compose -f docker-compose.prod.simple.yml logs -f frontend

# System resources
docker stats
```

### Check Tunnel Status

```bash
sudo systemctl status cloudflared
sudo journalctl -u cloudflared -f
```

## 🎯 Recommended Workflow

1. **Develop locally** on your Mac
2. **Test locally** with `docker-compose up`
3. **Commit changes** with descriptive messages
4. **Push to GitHub**
5. **Run deployment script**: `./deploy-github.sh`
6. **Verify** site is working at https://zeroqwait.com
7. **Monitor logs** if needed

## 🔐 GitHub Repository Setup

### Repository Settings

1. **Make it private** if it contains sensitive logic
2. **Add collaborators** if working with a team
3. **Set up branch protection** for `main` branch:
   - Require pull request reviews
   - Require status checks to pass

### Optional: GitHub Actions (CI/CD)

You can automate deployment with GitHub Actions. Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Raspberry Pi

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - name: Deploy to Pi
      uses: appleboy/ssh-action@master
      with:
        host: ${{ secrets.PI_HOST }}
        username: ${{ secrets.PI_USER }}
        key: ${{ secrets.SSH_PRIVATE_KEY }}
        script: |
          cd /home/pi/Documents/projects/apps/zeroqwait
          git pull origin main
          docker compose -f docker-compose.prod.simple.yml down
          docker compose -f docker-compose.prod.simple.yml build
          docker compose -f docker-compose.prod.simple.yml up -d
```

## 📝 Summary

✅ **Completed**:
- Project moved to `/home/pi/Documents/projects/apps/zeroqwait/`
- Old FastCuts directory deleted
- Deployment script created (`deploy-github.sh`)

🔨 **Next Steps**:
1. Set up GitHub repository
2. Initialize Git on Pi
3. Configure GitHub PAT for authentication
4. Test deployment with `./deploy-github.sh`

Your deployment workflow is now more professional and maintainable! 🎉
