# Self-Hosted GitHub Runner Setup

Since your Raspberry Pi is on your home network and not accessible from the internet, we'll set up a **self-hosted GitHub Actions runner** that runs directly on your Pi.

## 🎯 Why Self-Hosted?

- ✅ Your Pi is on a private home network (192.168.29.220)
- ✅ GitHub's cloud runners can't reach your Pi directly
- ✅ Self-hosted runner runs ON your Pi, so no network issues
- ✅ Faster deployments (no SSH needed)

## 📋 Setup Steps

### Step 1: Go to GitHub Runner Settings

1. Go to your GitHub repository
2. Click **Settings** (top menu)
3. Click **Actions** → **Runners** (left sidebar)
4. Click **New self-hosted runner** button
5. Select **Linux** and **ARM64**

GitHub will show you setup commands - **DON'T RUN THEM YET!** Follow the steps below instead.

### Step 2: Install Runner on Raspberry Pi

SSH into your Pi and run these commands:

```bash
# SSH into Pi
ssh pi@192.168.29.220

# Create a folder for the runner
mkdir -p ~/actions-runner && cd ~/actions-runner

# Download the latest runner package (ARM64 for Pi)
curl -o actions-runner-linux-arm64-2.311.0.tar.gz -L https://github.com/actions/runner/releases/download/v2.311.0/actions-runner-linux-arm64-2.311.0.tar.gz

# Extract the installer
tar xzf ./actions-runner-linux-arm64-2.311.0.tar.gz
```

### Step 3: Configure the Runner

You'll need a **registration token** from GitHub. Get it from:
- GitHub repo → Settings → Actions → Runners → New self-hosted runner

Then run:

```bash
# Configure the runner (replace TOKEN with the token from GitHub)
./config.sh --url https://github.com/YOUR_USERNAME/YOUR_REPO --token YOUR_TOKEN

# When prompted:
# - Runner group: Press Enter (default)
# - Runner name: zeroqwait-pi (or press Enter for default)
# - Runner labels: Press Enter (default)
# - Work folder: Press Enter (default)
```

### Step 4: Install Runner as a Service

This makes the runner start automatically on boot:

```bash
# Install the service
sudo ./svc.sh install pi

# Start the service
sudo ./svc.sh start

# Check status
sudo ./svc.sh status
```

### Step 5: Verify Runner is Connected

1. Go to GitHub repo → Settings → Actions → Runners
2. You should see your runner listed as **"Idle"** (green dot)
3. If you see it, you're ready!

### Step 6: Replace the Workflow File

The old workflow tried to SSH from GitHub's servers. The new one runs directly on your Pi.

```bash
# On your Mac
cd /Users/neekrish/FastCuts

# Remove old workflow
git rm .github/workflows/deploy.yml

# Add new self-hosted workflow
git add .github/workflows/deploy-selfhosted.yml

# Commit and push
git commit -m "Switch to self-hosted GitHub runner"
git push origin main
```

## ✅ Test the Deployment

After pushing, go to GitHub → **Actions** tab. You'll see the deployment running **on your Pi**!

You can also test manually:

```bash
# Make a small change
echo "\n# Test self-hosted deployment" >> README.md

# Commit and push
git add README.md
git commit -m "Test self-hosted deployment"
git push origin main

# Watch it deploy in GitHub Actions tab!
```

## 🔍 Monitoring

### Check Runner Status on Pi

```bash
ssh pi@192.168.29.220
sudo /home/pi/actions-runner/svc.sh status
```

### View Runner Logs

```bash
ssh pi@192.168.29.220
tail -f /home/pi/actions-runner/_diag/Runner_*.log
```

### Restart Runner

```bash
ssh pi@192.168.29.220
sudo /home/pi/actions-runner/svc.sh restart
```

## 🛠️ Troubleshooting

### Runner Shows Offline

```bash
# On Pi
sudo /home/pi/actions-runner/svc.sh restart
```

### Deployment Fails with Permission Error

```bash
# On Pi
sudo usermod -aG docker pi
sudo chown -R pi:pi /home/pi/Documents/projects/apps/zeroqwait
```

### Runner Not Starting on Boot

```bash
# On Pi
sudo systemctl enable actions.runner.YOUR-USERNAME-YOUR-REPO.zeroqwait-pi.service
sudo systemctl start actions.runner.YOUR-USERNAME-YOUR-REPO.zeroqwait-pi.service
```

### Need to Re-register Runner

If you need to change repos or re-register:

```bash
# On Pi
cd ~/actions-runner
sudo ./svc.sh stop
./config.sh remove --token YOUR_REMOVAL_TOKEN
# Then re-run Step 3 and 4
```

## 📊 How It Works

```
┌─────────────┐
│  Your Mac   │
│  (develop)  │
└──────┬──────┘
       │ git push
       ↓
┌─────────────┐
│   GitHub    │
│ (triggers)  │
└──────┬──────┘
       │ Sends job to runner
       ↓
┌─────────────┐
│Raspberry Pi │ ← Runner is HERE!
│(self-hosted)│   Pulls code, builds, deploys
└──────┬──────┘
       │
       ↓
┌─────────────┐
│zeroqwait.com│
│   (live)    │
└─────────────┘
```

The runner on your Pi:
1. Listens for jobs from GitHub
2. When you push, it receives the job
3. Runs the deployment commands locally
4. Updates your live site

## 🎉 Benefits

- ✅ **No SSH issues** - Everything runs locally on Pi
- ✅ **Faster** - No need to download/upload code over internet
- ✅ **More secure** - No need to expose SSH or open ports
- ✅ **Auto-start** - Runner starts on Pi boot
- ✅ **Reliable** - Direct execution, no network timeout issues

## 🔐 Security Notes

- The runner has access to your Pi, so only use it for your own repositories
- The runner runs as the `pi` user
- Keep your Pi and runner software updated
- Monitor the runner logs for suspicious activity

## 📝 Maintenance

### Update Runner

```bash
cd ~/actions-runner
sudo ./svc.sh stop
./config.sh remove --token YOUR_TOKEN
# Download new version and repeat Step 2-4
```

### Uninstall Runner

```bash
cd ~/actions-runner
sudo ./svc.sh stop
sudo ./svc.sh uninstall
./config.sh remove --token YOUR_TOKEN
cd ~
rm -rf ~/actions-runner
```

## ✅ Next Steps

After setup:
1. Verify runner shows "Idle" in GitHub
2. Push a commit to trigger deployment
3. Watch it deploy in Actions tab
4. Check https://zeroqwait.com to verify

Your deployment is now fully automated and reliable! 🚀
