#!/usr/bin/env bash
# Deploy frontend only to Cloud Run
# Usage: ./deploy_frontend.sh [BACKEND_URL]
# If BACKEND_URL not passed, it's read from the deployed backend service.
set -euo pipefail

PROJECT_ID="bnb-marathon-478217"
REGION="us-central1"
REPO="crowdgpt"
BACKEND_SERVICE="crowdgpt-backend"
FRONTEND_SERVICE="crowdgpt-frontend"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }

if [ ! -f backend/.env ]; then
  echo "ERROR: backend/.env not found. Run from project root."
  exit 1
fi

# Get backend URL (arg or from deployed service)
BACKEND_URL="${1:-}"
if [ -z "$BACKEND_URL" ]; then
  BACKEND_URL=$(gcloud run services describe "$BACKEND_SERVICE" \
    --region="$REGION" --project="$PROJECT_ID" \
    --format="value(status.url)" 2>/dev/null || echo "")
fi
if [ -z "$BACKEND_URL" ]; then
  echo "ERROR: Could not determine BACKEND_URL. Pass it as argument: ./deploy_frontend.sh https://..."
  exit 1
fi
info "Using BACKEND_URL=$BACKEND_URL"

info "Ensuring Artifact Registry repo '$REPO' exists..."
gcloud artifacts repositories describe "$REPO" \
  --project="$PROJECT_ID" --location="$REGION" &>/dev/null \
|| gcloud artifacts repositories create "$REPO" \
     --repository-format=docker \
     --location="$REGION" \
     --project="$PROJECT_ID" \
     --description="CrowdGPT container images"
success "Artifact Registry ready"

info "Building frontend image (VITE_API_URL=$BACKEND_URL)..."
FRONTEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/frontend:latest"
docker build \
  --build-arg "VITE_API_URL=${BACKEND_URL}" \
  -t "$FRONTEND_IMAGE" \
  -f frontend/Dockerfile \
  frontend/
docker push "$FRONTEND_IMAGE"
success "Frontend image pushed"

info "Deploying frontend to Cloud Run..."
gcloud run deploy "$FRONTEND_SERVICE" \
  --image="$FRONTEND_IMAGE" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --platform=managed \
  --allow-unauthenticated \
  --port=80 \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=1 \
  --max-instances=10

FRONTEND_URL=$(gcloud run services describe "$FRONTEND_SERVICE" \
  --region="$REGION" --project="$PROJECT_ID" \
  --format="value(status.url)")
success "Frontend deployed: $FRONTEND_URL"

info "Patching backend CORS with real frontend URL..."
gcloud run services update "$BACKEND_SERVICE" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --update-env-vars="\
FRONTEND_URL=${FRONTEND_URL},\
OAUTH_REDIRECT_URI=${BACKEND_URL}/auth/callback,\
ALLOWED_ORIGINS=${FRONTEND_URL}"
success "Backend CORS patched"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  CrowdGPT Frontend deployed!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Frontend:  ${CYAN}${FRONTEND_URL}${NC}"
echo -e "  Dashboard: ${CYAN}${FRONTEND_URL}/dashboard${NC}"
echo -e "  Backend:   ${CYAN}${BACKEND_URL}${NC}"
echo ""
echo -e "${YELLOW}ONE MANUAL STEP:${NC}"
echo -e "  Add to OAuth Authorized Redirect URIs:"
echo -e "  ${CYAN}${BACKEND_URL}/auth/callback${NC}"
echo -e "  -> https://console.cloud.google.com/apis/credentials"
echo ""
