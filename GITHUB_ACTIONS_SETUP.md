# GitHub Actions Auto-Deployment Setup

This guide walks you through setting up automatic deployment to your Raspberry Pi whenever you push code to the `main` branch.

## 🎯 What This Does

When you push code to GitHub's `main` branch, GitHub Actions will automatically:
1. Connect to your Raspberry Pi via SSH
2. Pull the latest code
3. Rebuild Docker containers
4. Restart services
5. Verify the deployment worked

## 📋 Setup Steps

### Step 1: Generate SSH Key for GitHub Actions

We need to create a dedicated SSH key that GitHub will use to connect to your Pi.

**On your Mac:**

```bash
# Generate a new SSH key specifically for GitHub Actions
ssh-keygen -t ed25519 -C "github-actions@zeroqwait" -f ~/.ssh/github_actions_pi

# This creates two files:
# ~/.ssh/github_actions_pi (private key - DO NOT SHARE)
# ~/.ssh/github_actions_pi.pub (public key - safe to share)
```

Press Enter when asked for a passphrase (leave it empty for automation).

### Step 2: Add Public Key to Raspberry Pi

**Copy the public key to your Pi:**

```bash
# Copy the public key
cat ~/.ssh/github_actions_pi.pub

# SSH into your Pi
ssh pi@192.168.29.220

# Add the public key to authorized_keys
mkdir -p ~/.ssh
nano ~/.ssh/authorized_keys
# Paste the public key on a new line, save and exit

# Set correct permissions
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys
exit
```

**Test the connection:**

```bash
# From your Mac
ssh -i ~/.ssh/github_actions_pi pi@192.168.29.220

# If it works without asking for a password, you're good! Exit and continue.
```

### Step 3: Get Private Key for GitHub Secrets

**On your Mac:**

```bash
# Display the private key
cat ~/.ssh/github_actions_pi

# Copy the ENTIRE output including:
# -----BEGIN OPENSSH PRIVATE KEY-----
# ... (all the lines)
# -----END OPENSSH PRIVATE KEY-----
```

**Copy this to your clipboard - you'll need it for GitHub Secrets.**

### Step 4: Configure GitHub Secrets

Go to your GitHub repository:

1. Click **Settings** (top navigation)
2. Click **Secrets and variables** → **Actions** (left sidebar)
3. Click **New repository secret**

Add these **three secrets**:

#### Secret 1: PI_HOST
- **Name**: `PI_HOST`
- **Value**: `192.168.29.220` (your Pi's local IP)
- Click **Add secret**

#### Secret 2: PI_USER
- **Name**: `PI_USER`
- **Value**: `pi` (your Pi username)
- Click **Add secret**

#### Secret 3: SSH_PRIVATE_KEY
- **Name**: `SSH_PRIVATE_KEY`
- **Value**: Paste the ENTIRE private key you copied earlier
- Click **Add secret**

### Step 5: Push the Workflow File

```bash
# On your Mac
cd /Users/neekrish/FastCuts

# Add the workflow file
git add .github/workflows/deploy.yml

# Commit
git commit -m "Add GitHub Actions auto-deployment workflow"

# Push to GitHub
git push origin main
```

### Step 6: Initialize Git on Raspberry Pi

If not already done:

```bash
# SSH into Pi
ssh pi@192.168.29.220

# Navigate to project
cd /home/pi/Documents/projects/apps/zeroqwait

# Initialize git if needed
git init

# Add remote
git remote add origin https://github.com/YOUR_USERNAME/zeroqwait.git

# Fetch and checkout
git fetch
git checkout main

# Configure git credentials
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

## ✅ Testing the Workflow

### Test 1: Manual Trigger

1. Go to your GitHub repository
2. Click **Actions** tab
3. Click **Deploy to Raspberry Pi** workflow
4. Click **Run workflow** → **Run workflow**
5. Watch the deployment in real-time!

### Test 2: Automatic Trigger

```bash
# On your Mac
cd /Users/neekrish/FastCuts

# Make a small change (e.g., edit README)
echo "\n# Test deployment" >> README.md

# Commit and push
git add README.md
git commit -m "Test automatic deployment"
git push origin main

# Go to GitHub → Actions tab to watch it deploy!
```

## 📊 Monitoring Deployments

### View Deployment Status

1. Go to GitHub repository
2. Click **Actions** tab
3. See all deployments and their status:
   - ✅ Green checkmark = Success
   - ❌ Red X = Failed
   - 🟡 Yellow circle = In progress

### View Deployment Logs

1. Click on any deployment
2. Click **Deploy to Production**
3. Expand each step to see detailed logs

### Get Notifications

GitHub will email you if a deployment fails (by default).

To customize notifications:
1. GitHub Profile → **Settings**
2. **Notifications**
3. Configure **Actions** notifications

## 🔧 Troubleshooting

### Deployment Fails with "Permission Denied"

**Problem**: SSH key not properly set up.

**Solution**:
```bash
# On Pi, check authorized_keys permissions
ls -la ~/.ssh/authorized_keys
# Should be: -rw------- (600)

# If not, fix it:
chmod 600 ~/.ssh/authorized_keys
```

### Deployment Fails with "git pull" Error

**Problem**: Git not configured or no write permissions.

**Solution**:
```bash
# On Pi
cd /home/pi/Documents/projects/apps/zeroqwait
sudo chown -R pi:pi .
git config credential.helper store
```

### Deployment Succeeds but Site Not Working

**Problem**: Cloudflared tunnel might need restart.

**Solution**:
```bash
# On Pi
sudo systemctl restart cloudflared
```

### Can't Connect to Pi from GitHub

**Problem**: Your home IP might be dynamic and changed, or firewall blocking.

**Solution**: 
- If using Cloudflare Tunnel, this shouldn't be needed
- GitHub Actions connects via your local network IP (192.168.29.220)
- Make sure your Pi is reachable from internet or consider using Cloudflare Tunnel's webhook approach

## 🔐 Security Best Practices

### ✅ DO:
- Use a dedicated SSH key for GitHub Actions
- Keep private keys in GitHub Secrets only
- Use SSH keys without passphrases for automation
- Regularly rotate SSH keys (every 6 months)
- Monitor Actions logs for suspicious activity

### ❌ DON'T:
- Never commit SSH private keys to Git
- Never share your GitHub Secrets
- Don't use your personal SSH key for automation
- Don't ignore failed deployment notifications

## 🚀 Advanced: Deployment Notifications

### Add Slack Notifications

Add to your workflow after the deployment step:

```yaml
- name: Slack Notification
  uses: 8398a7/action-slack@v3
  with:
    status: ${{ job.status }}
    text: 'Deployment to Raspberry Pi'
    webhook_url: ${{ secrets.SLACK_WEBHOOK }}
  if: always()
```

### Add Discord Notifications

```yaml
- name: Discord Notification
  uses: sarisia/actions-status-discord@v1
  if: always()
  with:
    webhook: ${{ secrets.DISCORD_WEBHOOK }}
    title: "Deployment Status"
    description: "Deployment to Raspberry Pi completed"
```

## 📝 Workflow File Explanation

The `.github/workflows/deploy.yml` file:

- **Triggers on**: Push to `main` branch or manual trigger
- **Runs on**: Ubuntu (GitHub's servers)
- **Steps**:
  1. **Checkout**: Gets your code
  2. **Deploy**: SSHs into Pi and runs deployment
  3. **Verify**: Tests that backend and frontend are responding
  4. **Notify**: Shows success/failure message

## 🎯 Workflow Customizations

### Deploy Only on Specific Paths

Only deploy when backend or frontend changes:

```yaml
on:
  push:
    branches: [ main ]
    paths:
      - 'backend/**'
      - 'frontend/**'
      - 'docker-compose.prod.simple.yml'
```

### Add Deployment Environments

For staging and production:

```yaml
jobs:
  deploy:
    environment:
      name: production
      url: https://zeroqwait.com
```

### Skip CI for Certain Commits

Add `[skip ci]` to commit message:

```bash
git commit -m "Update README [skip ci]"
```

## ✅ Success Checklist

After setup, verify:

- [ ] SSH key generated and added to Pi
- [ ] Three GitHub Secrets configured
- [ ] Workflow file pushed to repository
- [ ] Manual workflow run succeeds
- [ ] Automatic deployment works on push
- [ ] Site loads at https://zeroqwait.com
- [ ] API responds at https://zeroqwait.com/api

## 📊 Deployment Workflow

```
┌─────────────┐
│  Your Mac   │
│ (develop)   │
└──────┬──────┘
       │ git push
       ↓
┌─────────────┐
│   GitHub    │
│ (triggers)  │
└──────┬──────┘
       │ GitHub Actions
       ↓
┌─────────────┐
│ Raspberry Pi│
│  (deploy)   │
└──────┬──────┘
       │
       ↓
┌─────────────┐
│zeroqwait.com│
│   (live)    │
└─────────────┘
```

## 🎉 You're Done!

Now every time you push to `main`, your site will automatically deploy!

**Test it:**
```bash
git add .
git commit -m "Test auto-deployment"
git push origin main
# Watch it deploy in GitHub Actions tab!
```

Your deployment is now fully automated! 🚀
