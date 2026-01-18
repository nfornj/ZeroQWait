#!/bin/bash

# ZeroQwait Main Deployment Script
# Use this script to deploy to any environment

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         ZeroQwait Deployment - Choose Your Environment         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo "Select deployment environment:"
echo ""
echo "  1) Local Docker      (Development/Testing)"
echo "  2) Kubernetes        (Production)"
echo "  3) Docker Compose    (Production-like)"
echo "  4) View Logs         (Check running services)"
echo "  5) Cleanup           (Stop & remove containers)"
echo "  6) Monitoring        (Setup monitoring tools)"
echo ""
read -p "Enter choice (1-6): " choice
echo ""

case $choice in
  1)
    echo -e "${BLUE}🐳 Deploying to Local Docker...${NC}"
    bash ./scripts/deploy-local.sh
    ;;
  2)
    echo -e "${BLUE}☸️  Deploying to Kubernetes...${NC}"
    bash ./scripts/deploy-k8s.sh
    ;;
  3)
    echo -e "${BLUE}📦 Deploying with Docker Compose...${NC}"
    bash ./scripts/deploy-compose.sh
    ;;
  4)
    echo -e "${BLUE}📋 Showing Logs...${NC}"
    bash ./scripts/logs.sh
    ;;
  5)
    echo -e "${YELLOW}🗑️  Cleaning up...${NC}"
    bash ./scripts/cleanup.sh
    ;;
  6)
    echo -e "${BLUE}📊 Setting up Monitoring...${NC}"
    bash ./scripts/setup-monitoring.sh
    ;;
  *)
    echo -e "${RED}❌ Invalid choice!${NC}"
    exit 1
    ;;
esac
