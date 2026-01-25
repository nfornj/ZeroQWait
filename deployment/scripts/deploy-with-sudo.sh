#!/bin/bash
# Helper script that runs deploy with proper environment
# This script should be run with sudo on the remote server

export KUBECONFIG="/etc/rancher/k3s/k3s.yaml"
cd "$(dirname "$0")/../.." && bash deployment/scripts/deploy-k8s.sh
