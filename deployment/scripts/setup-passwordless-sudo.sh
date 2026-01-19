#!/bin/bash
# One-time setup script for passwordless deployment
# Run this once on your remote server

SUDO_FILE="/etc/sudoers.d/zeroqwait-deploy"

# Get the actual kubectl path
KUBECTL_PATH=$(which kubectl)
echo "Found kubectl at: $KUBECTL_PATH"

# Create sudoers entry
echo "Creating sudoers entry for passwordless sudo..."
echo "neekrishrichu ALL=(ALL) NOPASSWD: /bin/bash" | sudo tee "$SUDO_FILE" > /dev/null
echo "neekrishrichu ALL=(ALL) NOPASSWD: $KUBECTL_PATH" | sudo tee -a "$SUDO_FILE" > /dev/null

# Fix permissions
sudo chmod 440 "$SUDO_FILE"

# Verify
echo ""
echo "✅ Setup complete! Verifying..."
sudo -n bash -c "echo 'sudo works without password'" && echo "✅ Verification successful"
