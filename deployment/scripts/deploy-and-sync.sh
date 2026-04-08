#!/bin/bash
# ZeroQwait — Commit, push, and deploy (local machine)
#
# Usage:
#   bash deployment/scripts/deploy-and-sync.sh           # full deploy
#   bash deployment/scripts/deploy-and-sync.sh --no-push # skip git push
#
# Workflow:
#   1. Commit any uncommitted changes (auto-generates msg via Ollama if available)
#   2. Push to GitHub (optional, skipped with --no-push)
#   3. Run deploy-k8s.sh locally to build images + apply K8s manifests

set -e

SKIP_PUSH=false
for arg in "$@"; do [[ "$arg" == "--no-push" ]] && SKIP_PUSH=true; done

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   ZeroQwait — Commit + Deploy${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}  Project: $PROJECT_ROOT${NC}"
echo ""

# ── Sanity check ──────────────────────────────────────────────────────────
if ! command -v k3s &>/dev/null; then
    echo -e "${RED}✗ K3s not installed.${NC}"
    echo "  Run first: sudo bash deployment/scripts/bootstrap-server.sh"
    exit 1
fi

# ── Step 1: Git commit ────────────────────────────────────────────────────
echo -e "${BLUE}[1/3] Git...${NC}"

CURRENT_BRANCH=$(git -C "$PROJECT_ROOT" rev-parse --abbrev-ref HEAD)
UNCOMMITTED=$(git -C "$PROJECT_ROOT" status --porcelain | wc -l)

if [[ $UNCOMMITTED -gt 0 ]]; then
    echo -e "${YELLOW}  $UNCOMMITTED uncommitted file(s) on branch '${CURRENT_BRANCH}'${NC}"

    # Try to auto-generate commit message with Ollama
    COMMIT_MSG=""
    if command -v ollama &>/dev/null; then
        GIT_DIFF=$(git -C "$PROJECT_ROOT" diff --stat 2>/dev/null | head -5)
        PROMPT="Based on these changes, write ONE SHORT git commit message (max 60 chars). Output ONLY the message.\n\n$GIT_DIFF"
        COMMIT_MSG=$(echo -e "$PROMPT" | timeout 20 ollama run gpt-oss:20b 2>/dev/null \
            | grep -v "^>" | head -1 \
            | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' \
            | head -c 60) || true
    fi
    [[ ${#COMMIT_MSG} -lt 5 ]] && COMMIT_MSG="chore: update and deploy"

    echo -e "  Generated message: \"${COMMIT_MSG}\""
    read -p "  Use this? (y/n/custom) " -r REPLY
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        :  # use generated message
    elif [[ $REPLY =~ ^[Nn]$ ]]; then
        read -p "  Enter commit message: " COMMIT_MSG
    else
        COMMIT_MSG="$REPLY"
    fi

    git -C "$PROJECT_ROOT" add -A
    git -C "$PROJECT_ROOT" commit -m "$COMMIT_MSG"
    echo -e "${GREEN}  ✓ Committed: \"$COMMIT_MSG\"${NC}"
else
    echo -e "  ✓ Nothing to commit on branch '${CURRENT_BRANCH}'"
fi
echo ""

# ── Step 2: Git push ──────────────────────────────────────────────────────
if [[ $SKIP_PUSH == false ]]; then
    echo -e "${BLUE}[2/3] Pushing to GitHub...${NC}"
    git -C "$PROJECT_ROOT" push origin "$CURRENT_BRANCH" \
        && echo -e "${GREEN}  ✓ Pushed to origin/${CURRENT_BRANCH}${NC}" \
        || echo -e "${YELLOW}  ⚠  Push failed (continuing with local deploy)${NC}"
else
    echo -e "${YELLOW}[2/3] Skipping git push (--no-push)${NC}"
fi
echo ""

# ── Step 3: Local K8s deploy ──────────────────────────────────────────────
echo -e "${BLUE}[3/3] Deploying to local K3s...${NC}"
echo ""
bash "$SCRIPT_DIR/deploy-k8s.sh"

