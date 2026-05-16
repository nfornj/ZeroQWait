#!/usr/bin/env bash
# deploy-premium-shop.sh — provision and deploy a dedicated runtime for a premium shop
#
# Usage:
#   ./deploy-premium-shop.sh <SHOP_ID> <SHOP_SLUG> [IMAGE_TAG]
#
# Example:
#   ./deploy-premium-shop.sh 42 luxe-cuts v20260516005346-5794ab9
#
# The script:
#   1. Resolves the current backend image tag from the live deployment (if not passed)
#   2. Calls the platform provisioner API to assign dedicated runtime
#   3. Applies backend-shop, worker-shop, and configmap-shop K8s manifests
#   4. Adds an ingress rule so SHOP_SLUG.zeroqwait.com → backend-shop-SHOP_ID
#
# Requires:
#   - kubectl configured to zeroqwait namespace
#   - envsubst (part of gettext)
#   - curl + jq
#   - ADMIN_TOKEN env var (JWT for super_admin user)
set -euo pipefail

SHOP_ID=${1:?Usage: $0 <SHOP_ID> <SHOP_SLUG> [IMAGE_TAG]}
SHOP_SLUG=${2:?Usage: $0 <SHOP_ID> <SHOP_SLUG> [IMAGE_TAG]}
IMAGE_TAG=${3:-}

NS="zeroqwait"
TEMPLATE_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_URL="${BACKEND_URL:-http://localhost:30000}"
ADMIN_TOKEN="${ADMIN_TOKEN:?Set ADMIN_TOKEN to a super_admin JWT}"

# Resolve image tag from live backend deployment if not provided
if [[ -z "$IMAGE_TAG" ]]; then
  IMAGE_TAG=$(sudo kubectl get deployment/backend -n "$NS" -o jsonpath='{.spec.template.spec.containers[0].image}' | cut -d: -f2)
  echo "Using current backend image tag: $IMAGE_TAG"
fi

echo "==> Provisioning tenant schema and dedicated runtime for shop $SHOP_ID ($SHOP_SLUG)..."
curl -sf -X POST "$BACKEND_URL/api/platform/shops/$SHOP_ID/provision-schema" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .

curl -sf -X POST "$BACKEND_URL/api/platform/shops/$SHOP_ID/provision-premium" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .

echo "==> Applying K8s manifests for shop $SHOP_ID..."
export SHOP_ID SHOP_SLUG IMAGE_TAG

envsubst < "$TEMPLATE_DIR/configmap-shop.yaml" | sudo kubectl apply -f -
envsubst < "$TEMPLATE_DIR/backend-shop.yaml" | sudo kubectl apply -f -
envsubst < "$TEMPLATE_DIR/worker-shop.yaml" | sudo kubectl apply -f -

echo "==> Waiting for backend-shop-$SHOP_ID to be ready..."
sudo kubectl rollout status deployment/backend-shop-$SHOP_ID -n $NS --timeout=120s

echo "==> Runtime deployed. Verify:"
curl -sf "$BACKEND_URL/api/platform/shops/$SHOP_ID/runtime" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .

echo "DONE. Shop $SHOP_ID ($SHOP_SLUG) now has dedicated runtime."
