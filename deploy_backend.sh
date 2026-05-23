#!/usr/bin/env bash
# Deploy backend only to Cloud Run
set -euo pipefail

PROJECT_ID="bnb-marathon-478217"
REGION="us-central1"
REPO="crowdgpt"
BACKEND_SERVICE="crowdgpt-backend"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }

if [ ! -f backend/.env ]; then
  echo "ERROR: backend/.env not found. Run from project root."
  exit 1
fi
set -a; source backend/.env; set +a
success ".env loaded"

info "Ensuring Artifact Registry repo '$REPO' exists..."
gcloud artifacts repositories describe "$REPO" \
  --project="$PROJECT_ID" --location="$REGION" &>/dev/null \
|| gcloud artifacts repositories create "$REPO" \
     --repository-format=docker \
     --location="$REGION" \
     --project="$PROJECT_ID" \
     --description="CrowdGPT container images"
success "Artifact Registry ready"

info "Building backend image..."
BACKEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/backend:latest"
docker build -t "$BACKEND_IMAGE" -f backend/Dockerfile backend/
docker push "$BACKEND_IMAGE"
success "Backend image pushed"

# Get current frontend URL (or placeholder if not deployed yet)
FRONTEND_URL=$(gcloud run services describe crowdgpt-frontend \
  --region="$REGION" --project="$PROJECT_ID" \
  --format="value(status.url)" 2>/dev/null || echo "https://placeholder.run.app")

info "Deploying backend to Cloud Run..."
gcloud run deploy "$BACKEND_SERVICE" \
  --image="$BACKEND_IMAGE" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --platform=managed \
  --allow-unauthenticated \
  --port=8000 \
  --memory=2Gi \
  --cpu=2 \
  --min-instances=1 \
  --max-instances=10 \
  --startup-cpu-boost \
  --set-env-vars="\
GOOGLE_API_KEY=${GOOGLE_API_KEY},\
GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID},\
GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET},\
JWT_SECRET=${JWT_SECRET},\
SENDGRID_API_KEY=${SENDGRID_API_KEY},\
GEMINI_MODEL=${GEMINI_MODEL:-gemini-2.0-flash},\
GCP_PROJECT_ID=${PROJECT_ID},\
GCP_REGION=${REGION},\
GCS_BUCKET_NAME=${GCS_BUCKET_NAME:-crowdgpt-media-2026},\
ALERT_EMAIL_FROM=${ALERT_EMAIL_FROM},\
ALERT_EMAIL_TO=${ALERT_EMAIL_TO},\
ALLOWED_ADMINS=${ALLOWED_ADMINS:-},\
OPEN_ACCESS=true,\
ADMIN_ROLES=${ADMIN_ROLES:-},\
COOKIE_SECURE=true,\
FRONTEND_URL=${FRONTEND_URL},\
OAUTH_REDIRECT_URI=${FRONTEND_URL}/auth/callback,\
ALLOWED_ORIGINS=${FRONTEND_URL}"

BACKEND_URL=$(gcloud run services describe "$BACKEND_SERVICE" \
  --region="$REGION" --project="$PROJECT_ID" \
  --format="value(status.url)")
success "Backend deployed: $BACKEND_URL"

echo ""
echo -e "${YELLOW}If frontend is already deployed, patch CORS:${NC}"
echo -e "  ${CYAN}./patch_backend_cors.sh${NC}"
echo ""
echo -e "Backend API: ${CYAN}${BACKEND_URL}${NC}"
echo -e "Health check: ${CYAN}${BACKEND_URL}/health${NC}"
