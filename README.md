# CrowdGPT — Agentic Intelligence for Predictive Crowd Safety

> **Google Cloud Agentic Premier League Finale 2026**
>
> A real-time, multi-agent AI platform that monitors, predicts, and responds to crowd safety events at large-scale cricket stadiums — powered by Google ADK, Gemini 2.5 Flash, and Google Cloud Run.

---

## The Problem

Massive crowds at cricket matches (M. Chinnaswamy Stadium holds **40,000 fans**) create dangerous bottlenecks, security blind spots, and logistical chaos during pre- and post-match movements. Current stadium operations rely on **fragmented, manual systems** — leaving safety teams unable to react instantly to crowd surges, weather shifts, or emerging threats.

Operators need an integrated, AI-driven command platform that unifies crowd monitoring, dynamically routes fan flow, and automates emergency response — all in real time.

---

## The Solution

**CrowdGPT** is a multi-agent AI system built on **Google ADK** and powered by **Gemini 2.5 Flash**. A master Orchestrator Agent coordinates a team of specialist agents that continuously monitor crowd conditions, make routing decisions, detect threats, and execute emergency protocols — surfaced through a live operator dashboard with real-time camera feeds, YOLOv8 + LSTM detection, and zone-level density heatmaps.

---

## Live Demo

| Service | URL |
|---------|-----|
| **Operator Dashboard** | `https://crowdgpt-frontend-<hash>.run.app/dashboard` |
| **Backend API** | `https://crowdgpt-backend-<hash>.run.app` |
| **Broadcast Screen** | `https://crowdgpt-frontend-<hash>.run.app/screen` |

---

## Architecture

### Agent Hierarchy

```
┌──────────────────────────────────────────────────────────────────┐
│                       ORCHESTRATOR AGENT                         │
│                  (Google ADK — Gemini 2.5 Flash)                 │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │                 ParallelAgent — Monitoring                  │  │
│  │                                                            │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌─────────────────┐  │  │
│  │  │ Crowd Density│  │ Gate Sensor  │  │ Weather Context │  │  │
│  │  │    Agent     │  │    Agent     │  │     Agent       │  │  │
│  │  └──────┬───────┘  └──────┬───────┘  └───────┬─────────┘  │  │
│  └─────────┼─────────────────┼──────────────────┼────────────┘  │
│            └─────────────────┴──────────────────┘               │
│                              │ threshold breach (density > 65%)  │
│            ┌─────────────────▼────────────────────────────┐     │
│            │        SequentialAgent — Response Chain        │     │
│            │                                               │     │
│            │  [1] Routing Agent     → Gate commands        │     │
│            │  [2] Threat Detection  → Risk score 0-100     │     │
│            │  [3] Emergency Protocol→ Playbook activation  │     │
│            │  [4] Notifier Agent    → SendGrid email alerts│     │
│            └───────────────────────────────────────────────┘     │
└──────────────────────────────┬───────────────────────────────────┘
                               │  SSE stream
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                      OPERATOR DASHBOARD                          │
│  Stadium Heatmap │ YOLOv8+LSTM │ Agent Feed │ Gate Controls      │
└──────────────────────────────────────────────────────────────────┘
```

### Agent Responsibilities

| Agent | Role | ADK Pattern |
|-------|------|------------|
| **Orchestrator** | Master coordinator — delegates, manages state, escalates | `LlmAgent` |
| **Crowd Density** | Zone-level density, flow vectors, hotspot detection | `ParallelAgent` member |
| **Gate Sensor** | Gate throughput, bottleneck detection, queue depth | `ParallelAgent` member |
| **Weather Context** | Live weather via open-meteo API, flags conditions affecting crowd | `ParallelAgent` member |
| **Routing** | Gate open/close/redirect recommendations from density data | `SequentialAgent` step 1 |
| **Threat Detection** | Risk score 0–100, anomaly detection (surges, clustering) | `SequentialAgent` step 2 |
| **Emergency Protocol** | Triggers NORMAL / CAUTION / EVACUATE / LOCKDOWN playbooks | `SequentialAgent` step 3 |
| **Notifier** | Gemini-generated HTML alerts via SendGrid to operators + staff | `SequentialAgent` step 4 |

### Why This Architecture?

**Why ParallelAgent for monitoring?**
Crowd density, gate throughput, and weather are independent data streams. Running them in parallel reflects real stadium ops — you don't wait for one sensor before reading another.

**Why SequentialAgent for response?**
Response actions have strict ordering: routing decisions must precede threat assessment, which must precede protocol activation, which must precede notifications. Sequential ordering prevents conflicting instructions reaching the field.

**Why YOLO + LSTM?**
YOLO answers *"how many people are where right now?"* — a spatial, per-frame view. LSTM answers *"is this pattern anomalous given the last 30 seconds?"* — a temporal view. A crowd can be dense but stable (safe), or sparse but accelerating (dangerous). You need both lenses.

---

## Tech Stack

### Backend
| Component | Technology |
|-----------|-----------|
| Agent Framework | **Google ADK** (Agent Development Kit) |
| LLM | **Gemini 2.5 Flash** via Google AI Studio |
| API Server | **FastAPI + Uvicorn** |
| Auth | **Google OAuth 2.0** + JWT httpOnly cookie |
| Email Alerts | **SendGrid** — HTML email with zone data, anomalies, gate actions |
| Crowd Detection | **YOLOv8n + LSTM** — spatial detection + temporal anomaly |

### Frontend
| Component | Technology |
|-----------|-----------|
| Framework | **React 18 + TypeScript + Vite** |
| Styling | **Tailwind CSS** |
| Real-time | **SSE** (Server-Sent Events) for agent decision stream |
| Live Views | Stadium heatmap, YOLOv8+LSTM canvas, 4 GCS video feeds |
| Auth | Google OAuth → JWT cookie → `ProtectedRoute` |

### Google Cloud Platform

| Service | How it's used |
|---------|--------------|
| **Cloud Run** | Serverless container hosting for backend (FastAPI) and frontend (Nginx). Auto-scales to zero, min 1 instance kept warm for demo. |
| **Artifact Registry** | Docker image storage for both backend and frontend container images (`us-central1-docker.pkg.dev`). |
| **Secret Manager** | Stores all secrets at rest — `GOOGLE_API_KEY`, `GOOGLE_CLIENT_SECRET`, `JWT_SECRET`, `SENDGRID_API_KEY`. Mounted as env vars at Cloud Run runtime via `--set-secrets`. |
| **Cloud Storage (GCS)** | Hosts 4 stadium video feeds served directly via public GCS URLs (`storage.googleapis.com/crowdgpt-media-2026/videos/`). Also used as sensor data bus. |
| **Google OAuth 2.0** | Full OAuth 2.0 PKCE flow — Google consent screen → backend `/auth/callback` → JWT httpOnly cookie (`cg_session`). Role-based: `ADMIN` / `SUPER_ADMIN`. |
| **Gemini 2.5 Flash** | LLM backbone for all 8 agents via `google-generativeai` SDK. Used for operator message generation (Notifier), routing decisions, threat scoring, and emergency protocol selection. |
| **Google ADK** | Agent Development Kit — `LlmAgent`, `ParallelAgent`, `SequentialAgent` compose the full multi-agent hierarchy. |
| **Cloud Build** | CI/CD pipeline (`infra/cloudbuild.yaml`) — builds and deploys all services on `gcloud builds submit`. |
| **Open-Meteo API** | Free weather API called by the Weather Context agent for live Bangalore conditions (latitude 12.9792°N, longitude 77.5997°E). |

---

## Project Structure

```
crowdgpt/
├── backend/
│   ├── agent_orchestrator/
│   │   ├── main.py                # FastAPI app + all REST endpoints
│   │   ├── orchestrator.py        # Master orchestrator (ADK)
│   │   ├── auth.py                # Google OAuth 2.0 + JWT
│   │   ├── broadcast.py           # SSE broadcast manager
│   │   ├── agents/
│   │   │   ├── crowd_density.py
│   │   │   ├── gate_sensor.py
│   │   │   ├── weather_context.py
│   │   │   ├── routing.py
│   │   │   ├── threat_detection.py
│   │   │   ├── emergency.py
│   │   │   └── notifier.py        # Gemini-generated alert emails
│   │   └── tools/
│   │       ├── sensor_tools.py    # Simulated sensor data per phase
│   │       ├── gate_control.py    # Gate open/close state
│   │       └── alert_tools.py     # SendGrid dispatch + email template
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.tsx                # Routes + Dashboard layout
│   │   ├── api.ts                 # Typed fetch client
│   │   ├── components/
│   │   │   ├── LivePanel.tsx      # Stadium map, YOLO canvas, video feeds
│   │   │   ├── StadiumMap.tsx     # SVG zone heatmap
│   │   │   ├── AgentFeed.tsx      # Real-time decision stream
│   │   │   ├── GateControls.tsx   # Gate override panel
│   │   │   ├── AlertPanel.tsx     # Active alert list
│   │   │   └── StatusBar.tsx      # Header — phase, risk, protocol badge
│   │   ├── context/AuthContext.tsx
│   │   ├── hooks/
│   │   │   ├── useAgentStream.ts  # SSE subscription
│   │   │   └── useBroadcast.ts    # Broadcast screen SSE
│   │   └── pages/
│   │       ├── LoginPage.tsx
│   │       └── BroadcastScreen.tsx
│   ├── Dockerfile
│   └── vite.config.ts
├── infra/
│   ├── cloudbuild.yaml
│   └── docker-compose.yml
├── deploy.sh                      # One-shot Cloud Run deployment
└── README.md
```

---

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 20+
- Docker Desktop
- `gcloud` CLI authenticated

### Backend

```bash
cd backend
pip install -r requirements.txt

# Copy and fill in your keys
cp .env.example .env
# Required: GOOGLE_API_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
#           JWT_SECRET, SENDGRID_API_KEY, ALLOWED_ADMINS

cd agent_orchestrator
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install

# API URL for local dev (default)
echo "VITE_API_URL=http://localhost:8000" > .env.local

npm run dev
# → http://localhost:5173
```

### Environment Variables

Create `backend/.env` with:

```env
# Google AI
GOOGLE_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash

# Google OAuth
GOOGLE_CLIENT_ID=your_client_id
GOOGLE_CLIENT_SECRET=your_client_secret
OAUTH_REDIRECT_URI=http://localhost:8000/auth/callback

# Auth
JWT_SECRET=your_random_secret
ALLOWED_ADMINS=your@email.com
ADMIN_ROLES=your@email.com:SUPER_ADMIN

# Frontend
FRONTEND_URL=http://localhost:5173
ALLOWED_ORIGINS=http://localhost:5173

# SendGrid
SENDGRID_API_KEY=SG.your_key
ALERT_EMAIL_FROM=your_verified@email.com
ALERT_EMAIL_TO=your@email.com

# GCP
GCP_PROJECT_ID=your-project-id
GCS_BUCKET_NAME=your-bucket
COOKIE_SECURE=false
```

---

## Cloud Run Deployment

### How env vars are handled

| Type | Mechanism |
|------|-----------|
| **Secrets** (API keys, JWT, OAuth secret, SendGrid) | Google Secret Manager → mounted at runtime via `--set-secrets` |
| **Config** (email, admins, model name) | `--set-env-vars` on Cloud Run service |
| **Frontend** (`VITE_API_URL`) | Build arg baked into Nginx bundle at `docker build` time |

### Deploy (one command)

```bash
# 1. Authenticate
gcloud auth login
gcloud config set project bnb-marathon-478217
gcloud auth configure-docker us-central1-docker.pkg.dev

# 2. Run deploy script
./deploy.sh
```

The script:
1. Creates Artifact Registry repo if needed
2. Stores all secrets in Secret Manager (idempotent)
3. Builds + pushes backend image, deploys to Cloud Run
4. Builds + pushes frontend image with `VITE_API_URL` baked in, deploys to Cloud Run
5. Patches backend with real frontend URL (CORS + OAuth redirect)
6. Prints both URLs and the OAuth callback to register

### After deploy — one manual step

Add the backend callback URL to Google Cloud Console:
1. Go to [APIs & Credentials](https://console.cloud.google.com/apis/credentials)
2. Edit your OAuth 2.0 Client ID
3. Add to **Authorized redirect URIs**: `https://crowdgpt-backend-<hash>.run.app/auth/callback`

---

## Key Design Decisions

### Threshold-based escalation
The orchestrator only activates the response chain when crowd density exceeds 65% **or** a manual trigger is issued. Below threshold, monitoring agents run in continuous parallel — low cost, high visibility. This mirrors how real stadium ops centers work.

### Simulated sensor data
Each match phase (`pre_match`, `match_start`, `mid_match`, `match_end`, `post_match`) has distinct density profiles baked into `sensor_tools.py`. This guarantees a reliable, deterministic demo path without needing real hardware — while the agent reasoning and LLM decisions remain fully live.

### SendGrid email richness
Notifier agent uses Gemini to write the operator message text, then the email template injects: zone density table with capacity bars, anomaly list, gate reconfigurations, resources deployed, IST timestamp, and required actions. The email is fully self-contained — a safety officer on their phone gets everything they need.

### SSE over WebSocket
Server-Sent Events are simpler, reconnect automatically, and are one-directional (server → client) which matches the agent decision stream perfectly. No need for a persistent bidirectional channel.

---

## Rubric Alignment

| Criteria | How CrowdGPT addresses it |
|----------|--------------------------|
| **Functional Fulfillment (15 pts)** | End-to-end: density monitoring → routing → threat detection → emergency protocol → email alerts, all live |
| **Scalability & Security (10 pts)** | Cloud Run auto-scales (min 1, max 10 instances); **Secret Manager** for all credentials (zero secrets in code or images); **Google OAuth 2.0** with role-based access (ADMIN / SUPER_ADMIN); CORS locked to exact origins; httpOnly JWT cookie |
| **Static Code Analysis (15 pts)** | TypeScript strict mode throughout; Python typed with mypy-compatible patterns; Google ADK + Gemini SDK correct usage |
| **GCP Deployment Bonus (5 pts)** | Full Cloud Run deployment — backend + frontend, Secret Manager, Artifact Registry |
| **Innovation & Agentic Depth (15 pts)** | 8-agent hierarchy: ParallelAgent monitoring + SequentialAgent response chain; genuine LLM decision-making, not scripted flow |
| **Live Demo (10 pts)** | Phase-based simulated sensors ensure reliable demo; YOLO+LSTM canvas live-animates; agent feed shows real Gemini decisions |
| **Q&A Defense (15 pts)** | Every architectural decision documented above with rationale |

---

## Built With

- [Google Agent Development Kit (ADK)](https://github.com/google/adk-python)
- [Gemini 2.5 Flash](https://ai.google.dev/gemini-api/docs/models/gemini)
- [Google Cloud Run](https://cloud.google.com/run)
- [FastAPI](https://fastapi.tiangolo.com/)
- [React 18 + TypeScript](https://react.dev/)
- [YOLOv8 — Ultralytics](https://github.com/ultralytics/ultralytics)
- [SendGrid](https://sendgrid.com/)

---

*Built for Google Cloud Agentic Premier League Finale · IPL 2026 · M. Chinnaswamy Stadium, Bangalore*
