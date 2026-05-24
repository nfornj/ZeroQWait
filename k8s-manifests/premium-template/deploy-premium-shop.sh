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
#   3. Applies the full premium stack: dedicated Postgres, Redis, MCPs, backend, worker, ingress
#   4. Runs the dedicated database init job before moving compute onto the dedicated DB
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
MCP_IMAGE_TAG=${MCP_IMAGE_TAG:-}

NS="zeroqwait"
TEMPLATE_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_URL="${BACKEND_URL:-http://localhost:30000}"
ADMIN_TOKEN="${ADMIN_TOKEN:?Set ADMIN_TOKEN to a super_admin JWT}"
ENVSUBST_VARS='${SHOP_ID} ${SHOP_SLUG} ${IMAGE_TAG} ${BACKEND_IMAGE_TAG} ${MCP_IMAGE_TAG}'

# Resolve image tag from live backend deployment if not provided
if [[ -z "$IMAGE_TAG" ]]; then
  IMAGE_TAG=$(kubectl get deployment/backend -n "$NS" -o jsonpath='{.spec.template.spec.containers[0].image}' | cut -d: -f2)
  echo "Using current backend image tag: $IMAGE_TAG"
fi
if [[ -z "$MCP_IMAGE_TAG" ]]; then
  MCP_IMAGE_TAG=$(kubectl get deployment/booking-mcp -n "$NS" -o jsonpath='{.spec.template.spec.containers[0].image}' | cut -d: -f2)
  echo "Using current MCP image tag: $MCP_IMAGE_TAG"
fi

echo "==> Provisioning tenant schema and dedicated runtime for shop $SHOP_ID ($SHOP_SLUG)..."
curl -sf -X POST "$BACKEND_URL/api/platform/shops/$SHOP_ID/provision-schema" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .

curl -sf -X POST "$BACKEND_URL/api/platform/shops/$SHOP_ID/provision-premium" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .

echo "==> Applying K8s manifests for shop $SHOP_ID..."
export SHOP_ID SHOP_SLUG IMAGE_TAG BACKEND_IMAGE_TAG="$IMAGE_TAG" MCP_IMAGE_TAG

envsubst "$ENVSUBST_VARS" < "$TEMPLATE_DIR/configmap-shop.yaml" | kubectl apply -f -
envsubst "$ENVSUBST_VARS" < "$TEMPLATE_DIR/postgres-shop.yaml" | kubectl apply -f -
envsubst "$ENVSUBST_VARS" < "$TEMPLATE_DIR/redis-shop.yaml" | kubectl apply -f -

echo "==> Waiting for dedicated data services..."
kubectl rollout status statefulset/postgres-shop-$SHOP_ID -n "$NS" --timeout=180s
kubectl rollout status statefulset/redis-shop-$SHOP_ID -n "$NS" --timeout=120s

echo "==> Initializing dedicated database for shop $SHOP_ID..."
kubectl delete job db-init-shop-$SHOP_ID -n "$NS" --ignore-not-found
envsubst "$ENVSUBST_VARS" < "$TEMPLATE_DIR/db-init-job.yaml" | kubectl apply -f -
kubectl wait --for=condition=complete job/db-init-shop-$SHOP_ID -n "$NS" --timeout=300s

envsubst "$ENVSUBST_VARS" < "$TEMPLATE_DIR/mcp-shop.yaml" | kubectl apply -f -
envsubst "$ENVSUBST_VARS" < "$TEMPLATE_DIR/backend-shop.yaml" | kubectl apply -f -
envsubst "$ENVSUBST_VARS" < "$TEMPLATE_DIR/worker-shop.yaml" | kubectl apply -f -
envsubst "$ENVSUBST_VARS" < "$TEMPLATE_DIR/ingress-shop.yaml" | kubectl apply -f -

echo "==> Waiting for backend-shop-$SHOP_ID to be ready..."
kubectl rollout status deployment/backend-shop-$SHOP_ID -n "$NS" --timeout=180s
kubectl rollout status deployment/worker-shop-$SHOP_ID -n "$NS" --timeout=180s

echo "==> Runtime deployed. Verify:"
curl -sf "$BACKEND_URL/api/platform/shops/$SHOP_ID/runtime" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq .

echo "DONE. Shop $SHOP_ID ($SHOP_SLUG) now has dedicated runtime."
