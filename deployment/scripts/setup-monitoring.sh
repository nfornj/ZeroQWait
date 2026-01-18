#!/bin/bash

# Setup monitoring for ZeroQwait deployment
# Options: Prometheus + Grafana, or DataDog, or New Relic

set -e

# Colors
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${BLUE}📊 ZeroQwait Monitoring Setup${NC}"
echo "============================================================"
echo ""
echo "Select monitoring solution:"
echo ""
echo "  1) Prometheus + Grafana (Open-source, self-hosted)"
echo "  2) DataDog (Cloud-based, pay-per-use)"
echo "  3) New Relic (Cloud-based, full APM)"
echo "  4) ELK Stack (Elasticsearch + Logstash + Kibana)"
echo "  5) View Monitoring Recommendations"
echo ""
read -p "Enter choice (1-5): " choice
echo ""

case $choice in
  1)
    echo -e "${BLUE}Setting up Prometheus + Grafana...${NC}"
    bash ./prometheus-grafana.sh
    ;;
  2)
    echo -e "${BLUE}DataDog Integration Guide...${NC}"
    cat ../monitoring/datadog-setup.md
    ;;
  3)
    echo -e "${BLUE}New Relic Integration Guide...${NC}"
    cat ../monitoring/newrelic-setup.md
    ;;
  4)
    echo -e "${BLUE}Setting up ELK Stack...${NC}"
    bash ./elk-setup.sh
    ;;
  5)
    echo -e "${BLUE}📋 Monitoring Recommendations:${NC}"
    cat ../monitoring/MONITORING_GUIDE.md
    ;;
  *)
    echo "Invalid choice!"
    exit 1
    ;;
esac
