#!/bin/bash

# GitHub Actions Setup Helper Script
# This script helps you set up SSH keys for GitHub Actions deployment

set -e

echo "🔐 GitHub Actions SSH Key Setup"
echo "==============================="
echo ""

# Configuration
KEY_PATH="$HOME/.ssh/github_actions_pi"
PI_USER="pi"
PI_HOST="192.168.29.220"

# Step 1: Generate SSH Key
echo "📝 Step 1: Generating SSH Key..."
if [ -f "$KEY_PATH" ]; then
    echo "⚠️  SSH key already exists at $KEY_PATH"
    read -p "Do you want to overwrite it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping key generation..."
    else
        ssh-keygen -t ed25519 -C "github-actions@zeroqwait" -f "$KEY_PATH" -N ""
        echo "✅ New SSH key generated"
    fi
else
    ssh-keygen -t ed25519 -C "github-actions@zeroqwait" -f "$KEY_PATH" -N ""
    echo "✅ SSH key generated at $KEY_PATH"
fi
echo ""

# Step 2: Display Public Key
echo "📋 Step 2: Public Key (to add to Pi)"
echo "======================================"
echo ""
cat "${KEY_PATH}.pub"
echo ""
echo "Copy the above public key."
echo ""
read -p "Press Enter when ready to add it to your Pi..."

# Step 3: Add to Pi
echo ""
echo "🔧 Step 3: Adding public key to Raspberry Pi..."
ssh-copy-id -i "${KEY_PATH}.pub" "${PI_USER}@${PI_HOST}"

if [ $? -eq 0 ]; then
    echo "✅ Public key added to Pi"
else
    echo "❌ Failed to add public key. Please add it manually:"
    echo "   ssh ${PI_USER}@${PI_HOST}"
    echo "   mkdir -p ~/.ssh"
    echo "   echo '$(cat ${KEY_PATH}.pub)' >> ~/.ssh/authorized_keys"
    echo "   chmod 700 ~/.ssh"
    echo "   chmod 600 ~/.ssh/authorized_keys"
fi
echo ""

# Step 4: Test Connection
echo "🧪 Step 4: Testing SSH connection..."
if ssh -i "$KEY_PATH" -o BatchMode=yes -o ConnectTimeout=5 "${PI_USER}@${PI_HOST}" "echo 'Connection successful!'" > /dev/null 2>&1; then
    echo "✅ SSH connection works!"
else
    echo "❌ SSH connection failed. Please check your setup."
    exit 1
fi
echo ""

# Step 5: Display Private Key for GitHub Secrets
echo "🔑 Step 5: Private Key for GitHub Secrets"
echo "=========================================="
echo ""
echo "Go to your GitHub repository:"
echo "  Settings → Secrets and variables → Actions → New repository secret"
echo ""
echo "Add these THREE secrets:"
echo ""
echo "1. Name: PI_HOST"
echo "   Value: ${PI_HOST}"
echo ""
echo "2. Name: PI_USER"
echo "   Value: ${PI_USER}"
echo ""
echo "3. Name: SSH_PRIVATE_KEY"
echo "   Value: (copy the private key below)"
echo ""
echo "--- PRIVATE KEY (copy everything below) ---"
cat "$KEY_PATH"
echo ""
echo "--- END PRIVATE KEY ---"
echo ""
echo "⚠️  IMPORTANT: This is your PRIVATE key. Never share it or commit it to Git!"
echo ""
echo "✅ Setup complete! Follow these final steps:"
echo ""
echo "1. Add the three secrets to GitHub (as shown above)"
echo "2. Push the workflow file to GitHub:"
echo "     git add .github/workflows/deploy.yml"
echo "     git commit -m 'Add GitHub Actions deployment'"
echo "     git push origin main"
echo "3. Go to GitHub → Actions tab to see your first deployment!"
echo ""
echo "🎉 Your automated deployment is ready!"
