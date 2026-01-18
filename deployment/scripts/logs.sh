#!/bin/bash

# View logs for deployed services

set -e

# Colors
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}📋 Select what to view:${NC}"
echo ""
echo "  1) Docker - All logs"
echo "  2) Docker - Backend logs"
echo "  3) Docker - Frontend logs"
echo "  4) Kubernetes - All logs"
echo "  5) Kubernetes - Backend logs"
echo "  6) Kubernetes - Frontend logs"
echo ""
read -p "Enter choice (1-6): " choice
echo ""

case $choice in
  1)
    echo -e "${YELLOW}Showing all Docker logs (Ctrl+C to stop)${NC}"
    docker-compose logs -f
    ;;
  2)
    echo -e "${YELLOW}Showing backend logs (Ctrl+C to stop)${NC}"
    docker-compose logs -f backend
    ;;
  3)
    echo -e "${YELLOW}Showing frontend logs (Ctrl+C to stop)${NC}"
    docker-compose logs -f frontend
    ;;
  4)
    echo -e "${YELLOW}Showing all K8s logs (Ctrl+C to stop)${NC}"
    kubectl logs -n zeroqwait -f -l app=backend --tail=50 &
    kubectl logs -n zeroqwait -f -l app=frontend --tail=50 &
    wait
    ;;
  5)
    echo -e "${YELLOW}Showing K8s backend logs (Ctrl+C to stop)${NC}"
    kubectl logs -n zeroqwait -l app=backend -f --tail=100
    ;;
  6)
    echo -e "${YELLOW}Showing K8s frontend logs (Ctrl+C to stop)${NC}"
    kubectl logs -n zeroqwait -l app=frontend -f --tail=100
    ;;
  *)
    echo "Invalid choice!"
    exit 1
    ;;
esac
