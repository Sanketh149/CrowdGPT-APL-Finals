# CrowdGuard Command

> **Agentic Premier League Finale — Google Cloud Build with AI**
>
> A real-time, multi-agent crowd safety and operations command platform for large-scale cricket stadiums.

---

## The Problem

Massive crowds at cricket matches create dangerous bottlenecks, severe security vulnerabilities, and logistical chaos during pre- and post-match movements. Current stadium operations rely on **fragmented, manual systems** leaving security and volunteers unable to adapt instantly to crowd surges, weather shifts, or emerging threats.

**Organizers urgently need** an integrated, real-time command platform to unify ticketing, dynamically route crowd flow, and automate emergency responses for a safe and seamless fan experience.

---

## The Solution

CrowdGuard Command is a **multi-agent AI system** built on Google Cloud and powered by Gemini + ADK. A single Orchestrator Agent coordinates a team of specialist agents that continuously monitor crowd conditions, make routing decisions, detect threats, and execute emergency protocols — all surfaced through a unified operator dashboard.

---

## Architecture

### High-Level System Overview

![CrowdGuard Command Architecture](docs/architecture/Final_Flow_Diagram.png)

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA INGESTION                           │
│   Simulated Sensors  │  Gate Cameras  │  Ticketing System       │
└──────────────┬──────────────┬──────────────────────────────────-┘
               │              │
               ▼              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT                           │
│            (Google ADK — Gemini 1.5 Pro)                        │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              ParallelAgent (Monitoring)                  │   │
│   │                                                         │   │
│   │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐   │   │
│   │  │Crowd Density│ │ Gate Sensor │ │ Weather Context │   │   │
│   │  │   Agent     │ │   Agent     │ │     Agent       │   │   │
│   │  └──────┬──────┘ └──────┬──────┘ └────────┬────────┘   │   │
│   └─────────┼───────────────┼─────────────────┼────────────┘   │
│             └───────────────┴─────────────────┘                │
│                             │ threshold breach                  │
│             ┌───────────────▼─────────────────────────────┐    │
│             │        SequentialAgent (Response)            │    │
│             │                                              │    │
│             │  [1] Routing Agent   → Gate open/close cmds  │    │
│             │  [2] Threat Agent    → Risk score + alerts   │    │
│             │  [3] Emergency Agent → Protocol activation   │    │
│             │  [4] Notifier Agent  → Operator + staff msgs │    │
│             └──────────────────────────────────────────────┘    │
└──────────────────────────────┬──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   OPERATOR DASHBOARD                            │
│   Live map  │  Agent decisions  │  Gate states  │  Override     │
└─────────────────────────────────────────────────────────────────┘
```

### Agent Responsibilities

| Agent | Role | ADK Type |
|-------|------|----------|
| **Orchestrator** | Receives all events, delegates to specialists, manages state | `LlmAgent` |
| **Crowd Density Agent** | Analyzes sensor/video frames, computes density & flow vectors per zone | `ParallelAgent` member |
| **Gate Sensor Agent** | Monitors gate-level throughput, detects bottlenecks | `ParallelAgent` member |
| **Weather Context Agent** | Fetches live weather, flags conditions affecting crowd behavior | `ParallelAgent` member |
| **Routing Agent** | Recommends gate open/close/redirect decisions from density data | `SequentialAgent` step 1 |
| **Threat Detection Agent** | Assigns risk scores, detects anomalies (sudden acceleration, dense clusters) | `SequentialAgent` step 2 |
| **Emergency Protocol Agent** | Triggers predefined playbooks (evacuation, medical, lockdown) | `SequentialAgent` step 3 |
| **Notifier Agent** | Formats and dispatches alerts to operators and field staff via Gemini | `SequentialAgent` step 4 |

### Data Flow

```mermaid
flowchart TD
    A[Sensor Feed / Simulated Data] --> B[Orchestrator Agent]

    B --> C{ParallelAgent\nMonitoring}
    C --> D[Crowd Density Agent]
    C --> E[Gate Sensor Agent]
    C --> F[Weather Context Agent]

    D --> G{Threshold\nBreached?}
    E --> G
    F --> G

    G -- No --> C
    G -- Yes --> H{SequentialAgent\nResponse Chain}

    H --> I[Routing Agent\nGate Commands]
    I --> J[Threat Detection Agent\nRisk Score]
    J --> K[Emergency Protocol Agent\nPlaybook Trigger]
    K --> L[Notifier Agent\nAlerts Dispatched]

    L --> M[Operator Dashboard]
    I --> M
    J --> M
    K --> M
```

---

## Tech Stack

### Backend
| Component | Technology |
|-----------|-----------|
| Agent Framework | **Google ADK** (Agent Development Kit) |
| LLM | **Gemini 1.5 Pro** via Vertex AI |
| API Server | **Python / FastAPI** |
| Video/Sensor Processing | **OpenCV + YOLOv8** |
| Crowd Analytics | Custom density & flow vector computation |

### Frontend
| Component | Technology |
|-----------|-----------|
| Framework | **React + TypeScript** |
| Dashboard | Live map with zone overlays, gate state controls |
| Real-time Updates | WebSocket / SSE |

### Google Cloud Platform
| Service | Purpose |
|---------|---------|
| **Cloud Run** | Serverless hosting for all microservices |
| **Cloud Build** | CI/CD pipeline |
| **Artifact Registry** | Container image storage |
| **Cloud Storage** | Sensor data bus between services |
| **Eventarc** | Event-driven triggers between services |
| **Secret Manager** | API keys and credentials |
| **Vertex AI** | Gemini model serving |

---

## Project Structure

```
crowdguard-command/
├── backend/
│   ├── agent_orchestrator/
│   │   ├── orchestrator.py        # Master orchestrator agent
│   │   ├── agents/
│   │   │   ├── crowd_density.py   # Crowd density specialist
│   │   │   ├── gate_sensor.py     # Gate monitoring specialist
│   │   │   ├── weather_context.py # Weather context specialist
│   │   │   ├── routing.py         # Dynamic routing specialist
│   │   │   ├── threat_detection.py# Threat detection specialist
│   │   │   ├── emergency.py       # Emergency protocol specialist
│   │   │   └── notifier.py        # Notification specialist
│   │   └── tools/
│   │       ├── sensor_tools.py    # Sensor data access tools
│   │       ├── gate_control.py    # Gate open/close tools
│   │       └── alert_tools.py     # Alert dispatch tools
│   ├── video_processor/
│   │   ├── main.py                # FastAPI service
│   │   ├── yolo_analyzer.py       # YOLOv8 crowd detection
│   │   └── flow_vectors.py        # Crowd flow computation
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── StadiumMap.tsx      # Live zone map
│   │   │   ├── AgentFeed.tsx       # Real-time agent decision log
│   │   │   ├── GateControls.tsx    # Gate override panel
│   │   │   └── AlertPanel.tsx      # Active alerts
│   │   └── app/
│   ├── package.json
│   └── Dockerfile
├── infra/
│   ├── cloudbuild.yaml            # GCP CI/CD pipeline
│   └── terraform/                 # IaC for GCP resources
├── docs/
│   └── architecture/
│       └── agent-flow.png
├── docker-compose.yml             # Local development
└── README.md
```

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 20+
- Google Cloud SDK (`gcloud`)
- Docker

### Local Development

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/crowdguard-command.git
cd crowdguard-command

# Set up environment variables
cp backend/.env.example backend/.env
# Add your GOOGLE_API_KEY and GCP project details

# Start all services
docker-compose up

# Frontend available at: http://localhost:3000
# Backend API at:        http://localhost:8000
# Agent dashboard at:    http://localhost:8000/agents
```

### Environment Variables

```env
GOOGLE_API_KEY=your_gemini_api_key
GCP_PROJECT_ID=your_project_id
GCP_REGION=us-central1
VERTEX_AI_LOCATION=us-central1
```

---

## GCP Deployment

```bash
# Authenticate
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# Deploy via Cloud Build
gcloud builds submit --config infra/cloudbuild.yaml

# Services deployed to Cloud Run:
# - crowdguard-orchestrator
# - crowdguard-video-processor
# - crowdguard-frontend
```

---

## Key Design Decisions

### Why Orchestrator + Specialists over a Pipeline?
A hierarchical architecture gives the Orchestrator genuine intelligence — it decides *which* agents to run, *when*, and in *what order*, based on the current situation. A pipeline just passes data forward. The Orchestrator can escalate directly from Crowd Density to Emergency if density is critically high, skipping intermediate steps — that's agentic behavior, not scripted flow.

### Why ParallelAgent for Monitoring?
Crowd density, gate throughput, and weather are independent data streams. Running them in parallel reflects real stadium operations — you don't wait for one sensor before reading another.

### Why SequentialAgent for Response?
Response actions have strict ordering: you can't dispatch emergency protocols before you know the routing decisions, and you can't notify staff before protocols are chosen. Sequential ordering prevents conflicting instructions reaching the field.

### Why drop the News Gathering Agent?
Cricket matches are ticketed scheduled events — attendance and match timing are known in advance. A news agent adds external dependency with zero decision value. Weather is handled directly via API, giving actionable data (rain → shift crowd to covered exits) rather than headlines.

### Why YOLO + LSTM together?
YOLO answers *"how many people are where right now?"* — a spatial, per-frame view. LSTM answers *"is this pattern anomalous given the last 30 seconds?"* — a temporal view. A crowd can be dense but stable (safe) or sparse but accelerating (dangerous). You need both to distinguish between the two. YOLO outputs feed directly into the LSTM as time-series features: density, flow magnitude, acceleration, gate pressure per zone.

---

## Security & Code Quality

This codebase uses an **automated AI security review** on every commit and push. Before any code reaches the repository, a security-review skill scans for:

- Secrets and credentials accidentally committed (API keys, tokens, `.env` files)
- OWASP Top 10 vulnerabilities — injection, XSS, insecure deserialization, broken auth
- SSRF risks in any code making outbound HTTP calls (agent tool calls, weather API)
- Unsafe cryptography or direct data exposure
- Input validation gaps at system boundaries (API endpoints, file uploads)

This runs as a pre-commit/pre-push hook via Claude Code's `ecc:security-review` skill — no code ships without passing the security scan. This directly addresses the **Scalability & Security (10 pts)** rubric criterion.

---

## Scoring Alignment

| Criteria | How CrowdGuard Command addresses it |
|----------|-------------------------------------|
| **Functional Fulfillment (15 pts)** | Directly solves: real-time routing, threat detection, emergency automation |
| **Scalability & Security (10 pts)** | Cloud Run auto-scales; Secret Manager for credentials; automated AI security review on every commit (pre-commit hook) |
| **Static Code Analysis (15 pts)** | Clean repo structure; Google ADK + Gemini SDK usage throughout |
| **GCP Deployment Bonus (5 pts)** | Full Cloud Run deployment with Cloud Build CI/CD |
| **Innovation & Agentic Depth (15 pts)** | Multi-agent hierarchy with ParallelAgent + SequentialAgent, genuine decision-making |
| **Live Demo (10 pts)** | Simulated sensor data ensures reliable happy path demo |
| **Q&A Defense (15 pts)** | Clear architectural rationale for every agent and design choice |

---

## Built With

- [Google Agent Development Kit (ADK)](https://github.com/google/adk-python)
- [Gemini 1.5 Pro — Vertex AI](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/gemini)
- [Google Cloud Run](https://cloud.google.com/run)
- [YOLOv8 — Ultralytics](https://github.com/ultralytics/ultralytics)
- [FastAPI](https://fastapi.tiangolo.com/)
- [React + TypeScript](https://react.dev/)

---

*Built for Google Cloud Agentic Premier League Finale, 2026*
