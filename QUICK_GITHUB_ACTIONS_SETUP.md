# Quick GitHub Actions Setup (Using Existing SSH Key)

Since you already have SSH access to your Pi, setup is much simpler!

## ✅ What's Already Done

- ✅ SSH key exists on your Mac (`~/.ssh/id_rsa`)
- ✅ Public key is authorized on your Pi
- ✅ Passwordless SSH is working

## 🚀 3-Step Setup

### Step 1: Get Your Private Key

```bash
# Display your private key
cat ~/.ssh/id_rsa
```

**Copy the ENTIRE output** including:
- `-----BEGIN RSA PRIVATE KEY-----` or `-----BEGIN OPENSSH PRIVATE KEY-----`
- All the lines in between
- `-----END RSA PRIVATE KEY-----` or `-----END OPENSSH PRIVATE KEY-----`

### Step 2: Add GitHub Secrets

Go to your GitHub repository:

1. Click **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**

Add these **3 secrets**:

| Secret Name | Value |
|------------|-------|
| `PI_HOST` | `192.168.29.220` |
| `PI_USER` | `pi` |
| `SSH_PRIVATE_KEY` | (paste your private key from Step 1) |

### Step 3: Push the Workflow

```bash
cd /Users/neekrish/FastCuts

# Add the workflow file
git add .github/workflows/deploy.yml

# Commit and push
git commit -m "Add GitHub Actions auto-deployment"
git push origin main
```

## 🎉 That's It!

Go to your GitHub repository → **Actions** tab and you'll see your first deployment running!

## 🧪 Test It

Make a small change and push:

```bash
echo "\n# Auto-deploy test" >> README.md
git add README.md
git commit -m "Test auto-deployment"
git push origin main
```

Watch the **Actions** tab on GitHub to see it deploy automatically!

## 📊 What Happens Now

Every time you push to `main`:
1. GitHub triggers the workflow
2. Connects to your Pi via SSH
3. Pulls latest code
4. Rebuilds Docker containers
5. Restarts services
6. Verifies deployment

## 🔍 Monitoring

- **View all deployments**: GitHub → Actions tab
- **View logs**: Click on any deployment → Deploy to Production
- **Check Pi status**: `ssh pi@192.168.29.220` then `docker ps`

## ⚠️ Security Note

Your private SSH key is stored securely in GitHub Secrets. It's encrypted and only accessible during workflow runs. Never commit it to your repository!

## 🆘 Troubleshooting

### Deployment fails with "Permission denied"

Check if the key is correct:
```bash
# Test SSH connection
ssh pi@192.168.29.220 "echo 'Connected!'"
```

### Deployment succeeds but site not updating

```bash
# SSH into Pi and check
ssh pi@192.168.29.220
cd /home/pi/Documents/projects/apps/zeroqwait
git status
docker ps
```

### Want to trigger deployment manually?

Go to GitHub → Actions → Deploy to Raspberry Pi → Run workflow

---

**Your deployment is now fully automated!** 🚀

Push to `main` = Instant deployment to https://zeroqwait.com
