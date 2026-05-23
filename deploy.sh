#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# CrowdGPT — Cloud Run Deployment Script
# Passes all secrets as env vars directly (no Secret Manager required).
#
# Prerequisites:
#   gcloud auth login
#   gcloud config set project bnb-marathon-478217
#   gcloud auth configure-docker us-central1-docker.pkg.dev
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

PROJECT_ID="bnb-marathon-478217"
REGION="us-central1"
REPO="crowdgpt"
BACKEND_SERVICE="crowdgpt-backend"
FRONTEND_SERVICE="crowdgpt-frontend"

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
info()    { echo -e "${CYAN}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }

# ─────────────────────────────────────────────────────────────────────────────
# Load .env
# ─────────────────────────────────────────────────────────────────────────────
if [ ! -f backend/.env ]; then
  echo "ERROR: backend/.env not found. Run from project root."
  exit 1
fi
set -a; source backend/.env; set +a
success ".env loaded"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1 — Artifact Registry
# ─────────────────────────────────────────────────────────────────────────────
info "Ensuring Artifact Registry repo '$REPO' exists..."
gcloud artifacts repositories describe "$REPO" \
  --project="$PROJECT_ID" --location="$REGION" &>/dev/null \
|| gcloud artifacts repositories create "$REPO" \
     --repository-format=docker \
     --location="$REGION" \
     --project="$PROJECT_ID" \
     --description="CrowdGPT container images"
success "Artifact Registry ready"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2 — Build & deploy backend
# ─────────────────────────────────────────────────────────────────────────────
info "Building backend image..."
BACKEND_IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/backend:latest"
docker build -t "$BACKEND_IMAGE" -f backend/Dockerfile backend/
docker push "$BACKEND_IMAGE"
success "Backend image pushed"

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
  --set-env-vars="\
GOOGLE_API_KEY=${GOOGLE_API_KEY},\
GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID},\
GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET},\
JWT_SECRET=${JWT_SECRET},\
SENDGRID_API_KEY=${SENDGRID_API_KEY},\
GEMINI_MODEL=${GEMINI_MODEL},\
GCP_PROJECT_ID=${PROJECT_ID},\
GCP_REGION=${REGION},\
GCS_BUCKET_NAME=${GCS_BUCKET_NAME},\
ALERT_EMAIL_FROM=${ALERT_EMAIL_FROM},\
ALERT_EMAIL_TO=${ALERT_EMAIL_TO},\
ALLOWED_ADMINS=${ALLOWED_ADMINS},\
OPEN_ACCESS=true,\
ADMIN_ROLES=${ADMIN_ROLES},\
COOKIE_SECURE=true,\
FRONTEND_URL=https://placeholder.run.app,\
OAUTH_REDIRECT_URI=https://placeholder.run.app/auth/callback,\
ALLOWED_ORIGINS=https://placeholder.run.app"

BACKEND_URL=$(gcloud run services describe "$BACKEND_SERVICE" \
  --region="$REGION" --project="$PROJECT_ID" \
  --format="value(status.url)")
success "Backend deployed: $BACKEND_URL"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3 — Build & deploy frontend (bake backend URL into Vite bundle)
# ─────────────────────────────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4 — Patch backend with real frontend URL
# ─────────────────────────────────────────────────────────────────────────────
info "Patching backend with real frontend URL..."
gcloud run services update "$BACKEND_SERVICE" \
  --region="$REGION" \
  --project="$PROJECT_ID" \
  --update-env-vars="\
FRONTEND_URL=${FRONTEND_URL},\
OAUTH_REDIRECT_URI=${BACKEND_URL}/auth/callback,\
ALLOWED_ORIGINS=${FRONTEND_URL}"
success "Backend patched"

# ─────────────────────────────────────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  CrowdGPT deployed!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Frontend:  ${CYAN}${FRONTEND_URL}${NC}"
echo -e "  Backend:   ${CYAN}${BACKEND_URL}${NC}"
echo -e "  Dashboard: ${CYAN}${FRONTEND_URL}/dashboard${NC}"
echo ""
echo -e "${YELLOW}ONE MANUAL STEP:${NC}"
echo -e "  Add this to your OAuth client's Authorized Redirect URIs:"
echo -e "  ${CYAN}${BACKEND_URL}/auth/callback${NC}"
echo -e "  → https://console.cloud.google.com/apis/credentials"
echo ""
