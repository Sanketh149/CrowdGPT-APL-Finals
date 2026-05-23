# Auth + SendGrid + Broadcast Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Google OAuth admin login, role-based route protection, SendGrid email alerts to field staff, and a stadium broadcast screen that flips to full-screen emergency announcements via SSE.

**Architecture:** Google OAuth 2.0 flow handled entirely in the backend (FastAPI) — frontend redirects to `/auth/login`, backend exchanges code for token, verifies email against `ALLOWED_ADMINS`, issues a signed JWT stored in an httpOnly cookie. Frontend reads a `/auth/me` endpoint on load to hydrate user state. The broadcast screen is a separate unauthenticated React route `/screen` that subscribes to a `/broadcast/stream` SSE endpoint and flips full-screen on EVACUATE/LOCKDOWN protocol.

**Tech Stack:** `authlib` (Google OAuth), `python-jose` (JWT), `sendgrid` (email), React Context (auth state), React Router (protected routes), Tailwind CSS (login + broadcast UI)

---

## File Map

### New files
- `backend/agent_orchestrator/auth.py` — Google OAuth flow, JWT issue/verify, ALLOWED_ADMINS check
- `backend/agent_orchestrator/broadcast.py` — SSE broadcast manager, `/broadcast/stream` endpoint logic
- `frontend/src/context/AuthContext.tsx` — React context: user, role, loading, logout
- `frontend/src/pages/LoginPage.tsx` — Login page with Google OAuth button
- `frontend/src/pages/BroadcastScreen.tsx` — Unauthenticated stadium display screen
- `frontend/src/components/ProtectedRoute.tsx` — Wraps routes, redirects to /login if not authed
- `frontend/src/hooks/useBroadcast.ts` — SSE hook for broadcast stream

### Modified files
- `backend/agent_orchestrator/main.py` — Add `/auth/*`, `/broadcast/stream` endpoints, JWT middleware
- `backend/agent_orchestrator/tools/alert_tools.py` — Add `_send_sendgrid_email()` in `_attempt_real_dispatch`
- `backend/agent_orchestrator/agents/notifier.py` — Pass zone-specific context to email content
- `frontend/src/App.tsx` — Wrap with `AuthProvider`, add `ProtectedRoute`, add `/screen` route
- `frontend/src/types.ts` — Add `User`, `AuthState` interfaces
- `frontend/.env.example` — Add `VITE_API_URL`
- `backend/.env.example` — Add `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `JWT_SECRET`, `ALLOWED_ADMINS`, `SENDGRID_API_KEY`, `ALERT_EMAIL_TO`, `ALERT_EMAIL_FROM`

---

## Task 1: Backend — Auth module (Google OAuth + JWT)

**Files:**
- Create: `backend/agent_orchestrator/auth.py`
- Modify: `backend/.env.example`

- [ ] **Step 1: Install auth dependencies**

```bash
cd backend
pip install authlib httpx python-jose[cryptography] python-multipart
```

Add to `backend/requirements.txt`:
```
authlib==1.3.0
httpx==0.27.0
python-jose[cryptography]==3.3.0
python-multipart==0.0.9
```

- [ ] **Step 2: Create `backend/agent_orchestrator/auth.py`**

```python
"""
Google OAuth 2.0 + JWT session management for CrowdGuard Command.
Only emails in ALLOWED_ADMINS are granted access.
"""
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx
from jose import JWTError, jwt
from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "http://localhost:8000/auth/callback")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 8

ALLOWED_ADMINS: set[str] = set(
    e.strip().lower()
    for e in os.getenv("ALLOWED_ADMINS", "").split(",")
    if e.strip()
)

ROLE_MAP: dict[str, str] = {
    e.strip().lower(): role.strip()
    for entry in os.getenv("ADMIN_ROLES", "").split(",")
    if ":" in entry
    for e, role in [entry.strip().split(":", 1)]
}


def get_google_auth_url(state: str = "") -> str:
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
        "prompt": "select_account",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GOOGLE_AUTH_URL}?{query}"


async def exchange_code_for_user(code: str) -> dict:
    """Exchange OAuth code for user info. Raises HTTPException if unauthorized."""
    async with httpx.AsyncClient() as client:
        # Exchange code for tokens
        token_resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        })
        if token_resp.status_code != 200:
            raise HTTPException(status_code=401, detail="OAuth token exchange failed")
        tokens = token_resp.json()

        # Fetch user info
        user_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        if user_resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Failed to fetch user info")
        user = user_resp.json()

    email = user.get("email", "").lower()

    if ALLOWED_ADMINS and email not in ALLOWED_ADMINS:
        logger.warning(f"Unauthorized login attempt: {email}")
        raise HTTPException(status_code=403, detail=f"Access denied: {email} is not an authorized admin")

    role = ROLE_MAP.get(email, "OPERATOR")
    return {"email": email, "name": user.get("name", ""), "picture": user.get("picture", ""), "role": role}


def create_jwt(user: dict) -> str:
    payload = {
        **user,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid session: {e}")


def get_current_user(request: Request) -> dict:
    """Extract and verify JWT from cookie. Raises 401 if missing/invalid."""
    token = request.cookies.get("cg_session")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_jwt(token)


def require_super_admin(request: Request) -> dict:
    user = get_current_user(request)
    if user.get("role") != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="SUPER_ADMIN role required")
    return user
```

- [ ] **Step 3: Update `backend/.env.example`**

```env
# Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
OAUTH_REDIRECT_URI=http://localhost:8000/auth/callback

# JWT
JWT_SECRET=change-this-to-a-random-64-char-string-in-production

# Admin access — comma separated emails
ALLOWED_ADMINS=you@gmail.com,teammate@gmail.com
# Optional role overrides (default role is OPERATOR)
# SUPER_ADMIN gets gate override + emergency trigger
ADMIN_ROLES=you@gmail.com:SUPER_ADMIN

# SendGrid
SENDGRID_API_KEY=SG.your_key_here
ALERT_EMAIL_FROM=alerts@crowdguard.demo
ALERT_EMAIL_TO=fieldstaff@crowdguard.demo,commander@crowdguard.demo
```

- [ ] **Step 4: Commit**

```bash
git add backend/agent_orchestrator/auth.py backend/.env.example backend/requirements.txt
git commit -m "feat: add Google OAuth + JWT auth module"
```

---

## Task 2: Backend — Auth routes in main.py

**Files:**
- Modify: `backend/agent_orchestrator/main.py`

- [ ] **Step 1: Add auth imports and routes to `main.py`**

Add to imports at top:
```python
from fastapi import Depends, Cookie
from fastapi.responses import RedirectResponse, JSONResponse
from auth import (
    get_google_auth_url, exchange_code_for_user,
    create_jwt, get_current_user, require_super_admin
)
```

Add these routes after the existing `/health` route:
```python
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

@app.get("/auth/login")
async def auth_login():
    """Redirect to Google OAuth consent screen."""
    url = get_google_auth_url(state="crowdguard")
    return RedirectResponse(url)


@app.get("/auth/callback")
async def auth_callback(code: str, state: str = ""):
    """Handle Google OAuth callback — issue JWT cookie and redirect to dashboard."""
    user = await exchange_code_for_user(code)
    token = create_jwt(user)
    response = RedirectResponse(url=f"{FRONTEND_URL}/dashboard")
    response.set_cookie(
        key="cg_session",
        value=token,
        httponly=True,
        secure=False,  # set True in production with HTTPS
        samesite="lax",
        max_age=8 * 3600,
    )
    logger.info(f"Login success: {user['email']} ({user['role']})")
    return response


@app.get("/auth/me")
async def auth_me(request: Request):
    """Return current user from JWT cookie — 401 if not authenticated."""
    user = get_current_user(request)
    return {"email": user["email"], "name": user["name"], "picture": user["picture"], "role": user["role"]}


@app.post("/auth/logout")
async def auth_logout():
    response = JSONResponse({"success": True})
    response.delete_cookie("cg_session")
    return response
```

- [ ] **Step 2: Protect gate override with role check**

Replace the existing `override_gate` route signature:
```python
@app.post("/gate/{gate_id}/override")
async def override_gate(gate_id: str, action: str, request: Request):
    user = require_super_admin(request)
    if action not in ("open", "close"):
        raise HTTPException(status_code=400, detail="action must be 'open' or 'close'")
    result = await orchestrator.override_gate(gate_id=gate_id, action=action)
    logger.info(f"Gate override by {user['email']}: {gate_id} → {action}")
    return result
```

- [ ] **Step 3: Commit**

```bash
git add backend/agent_orchestrator/main.py
git commit -m "feat: add /auth/login, /auth/callback, /auth/me, /auth/logout routes"
```

---

## Task 3: Backend — SendGrid email dispatch

**Files:**
- Modify: `backend/agent_orchestrator/tools/alert_tools.py`

- [ ] **Step 1: Install sendgrid**

```bash
pip install sendgrid==6.11.0
```

Add to `backend/requirements.txt`:
```
sendgrid==6.11.0
```

- [ ] **Step 2: Replace `_attempt_real_dispatch` in `alert_tools.py`**

Replace the entire `_attempt_real_dispatch` function:
```python
def _attempt_real_dispatch(alert: dict) -> str:
    """Deliver alert via SendGrid email, Pub/Sub, webhook, or simulation."""

    # 1. SendGrid email (primary for field_staff and public_pa)
    sendgrid_key = os.getenv("SENDGRID_API_KEY")
    if sendgrid_key and alert["channel"] in ("field_staff", "public_pa", "all"):
        status = _send_sendgrid_email(alert, sendgrid_key)
        if status == "delivered_email":
            return status

    # 2. Pub/Sub fallback
    pubsub_topic = os.getenv("ALERT_PUBSUB_TOPIC")
    if pubsub_topic:
        try:
            from google.cloud import pubsub_v1
            publisher = pubsub_v1.PublisherClient()
            future = publisher.publish(pubsub_topic, data=json.dumps(alert).encode())
            future.result(timeout=5)
            return "delivered_pubsub"
        except Exception as e:
            logger.warning(f"Pub/Sub dispatch failed: {e}")

    # 3. Webhook fallback
    webhook_url = os.getenv("ALERT_WEBHOOK_URL")
    if webhook_url:
        try:
            import httpx
            resp = httpx.post(webhook_url, json=alert, timeout=5.0)
            if resp.status_code == 200:
                return "delivered_webhook"
        except Exception as e:
            logger.warning(f"Webhook dispatch failed: {e}")

    return "simulated"


def _send_sendgrid_email(alert: dict, api_key: str) -> str:
    """Send alert email via SendGrid. Returns 'delivered_email' or logs warning."""
    try:
        import sendgrid as sg_module
        from sendgrid.helpers.mail import Mail, To

        from_email = os.getenv("ALERT_EMAIL_FROM", "alerts@crowdguard.demo")
        to_emails_raw = os.getenv("ALERT_EMAIL_TO", "")
        to_emails = [e.strip() for e in to_emails_raw.split(",") if e.strip()]
        if not to_emails:
            logger.warning("ALERT_EMAIL_TO not configured — skipping email")
            return "skipped_no_recipient"

        severity_emoji = {"INFO": "ℹ️", "WARNING": "⚠️", "CRITICAL": "🚨"}.get(alert["severity"], "📢")
        subject = f"{severity_emoji} CrowdGuard [{alert['severity']}] — {alert['channel'].replace('_', ' ').title()}"

        actions_html = "".join(f"<li>{a}</li>" for a in (alert.get("actions_required") or []))
        zone_line = f"<p><strong>Zone:</strong> {alert['zone_id']}</p>" if alert.get("zone_id") else ""

        html_body = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;border:2px solid {'#dc2626' if alert['severity']=='CRITICAL' else '#f59e0b' if alert['severity']=='WARNING' else '#3b82f6'};border-radius:8px;overflow:hidden">
          <div style="background:{'#dc2626' if alert['severity']=='CRITICAL' else '#f59e0b' if alert['severity']=='WARNING' else '#3b82f6'};color:white;padding:16px 20px">
            <h2 style="margin:0">{severity_emoji} CrowdGuard Command Alert</h2>
            <p style="margin:4px 0 0;opacity:0.9">{alert['severity']} — {alert['channel'].replace('_',' ').title()}</p>
          </div>
          <div style="padding:20px;background:#fff">
            <p style="font-size:16px;color:#111">{alert['message']}</p>
            {zone_line}
            <p><strong>Time:</strong> {alert['timestamp']}</p>
            <p><strong>Alert ID:</strong> {alert['alert_id']}</p>
            {'<p><strong>Required Actions:</strong></p><ul style="color:#dc2626">' + actions_html + '</ul>' if actions_html else ''}
          </div>
          <div style="background:#f3f4f6;padding:10px 20px;font-size:12px;color:#6b7280">
            CrowdGuard Command · Narendra Modi Stadium · IPL 2026 Final
          </div>
        </div>
        """

        sg = sg_module.SendGridAPIClient(api_key=api_key)
        message = Mail(
            from_email=from_email,
            to_emails=to_emails,
            subject=subject,
            html_content=html_body,
        )
        response = sg.send(message)
        if response.status_code in (200, 202):
            logger.info(f"SendGrid email delivered to {to_emails}: {alert['alert_id']}")
            return "delivered_email"
        else:
            logger.warning(f"SendGrid returned {response.status_code}")
            return "simulated"
    except Exception as e:
        logger.warning(f"SendGrid dispatch failed: {e}")
        return "simulated"
```

- [ ] **Step 3: Commit**

```bash
git add backend/agent_orchestrator/tools/alert_tools.py backend/requirements.txt
git commit -m "feat: add SendGrid email dispatch for field_staff and public_pa alerts"
```

---

## Task 4: Backend — Broadcast SSE endpoint

**Files:**
- Create: `backend/agent_orchestrator/broadcast.py`
- Modify: `backend/agent_orchestrator/main.py`

- [ ] **Step 1: Create `backend/agent_orchestrator/broadcast.py`**

```python
"""
Broadcast Manager — pushes emergency announcements to all connected stadium screens.
Any screen (scoreboard, concourse display) subscribes to /broadcast/stream SSE.
When NotifierAgent fires a public_pa alert, all screens flip to full-screen message.
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import AsyncGenerator

logger = logging.getLogger(__name__)


class BroadcastManager:
    """Manages SSE connections for stadium display screens."""

    def __init__(self):
        self._queues: list[asyncio.Queue] = []
        self._latest: dict | None = None

    def _new_queue(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=10)
        self._queues.append(q)
        return q

    def _remove_queue(self, q: asyncio.Queue):
        try:
            self._queues.remove(q)
        except ValueError:
            pass

    async def broadcast(self, event: dict):
        """Push event to all connected screens."""
        self._latest = event
        dead = []
        for q in self._queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._remove_queue(q)
        logger.info(f"Broadcast pushed to {len(self._queues)} screen(s): {event.get('type')}")

    async def stream(self) -> AsyncGenerator[str, None]:
        """SSE generator for a single screen connection."""
        q = self._new_queue()
        # Send latest state immediately on connect (so a screen that just loaded gets current protocol)
        if self._latest:
            yield f"data: {json.dumps(self._latest)}\n\n"
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=25.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Keepalive ping every 25s to prevent proxy timeouts
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            self._remove_queue(q)

    @property
    def connected_screens(self) -> int:
        return len(self._queues)


# Singleton — imported by main.py and notifier
broadcast_manager = BroadcastManager()
```

- [ ] **Step 2: Add `/broadcast/stream` endpoint and broadcast trigger to `main.py`**

Add import:
```python
from broadcast import broadcast_manager
```

Add route:
```python
@app.get("/broadcast/stream")
async def broadcast_stream():
    """
    Unauthenticated SSE endpoint — stadium screens subscribe here.
    Receives protocol changes and PA announcements.
    """
    return StreamingResponse(
        broadcast_manager.stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/broadcast/status")
async def broadcast_status():
    return {
        "connected_screens": broadcast_manager.connected_screens,
        "timestamp": datetime.utcnow().isoformat(),
    }
```

- [ ] **Step 3: Wire broadcast into `/run` endpoint**

In the `run_orchestrator` function, after `result = await orchestrator.run(...)`, add:
```python
        # Push protocol change to all connected screens
        if result.get("protocol") in ("EVACUATE", "LOCKDOWN"):
            pa_alerts = [
                a for a in result.get("alerts", [])
                if a.get("channel") == "public_pa"
            ]
            await broadcast_manager.broadcast({
                "type": "emergency",
                "protocol": result["protocol"],
                "timestamp": datetime.utcnow().isoformat(),
                "message": pa_alerts[0]["message"] if pa_alerts else "Emergency protocol activated. Please follow staff instructions.",
                "open_gates": result.get("open_gates", []),
                "run_id": result["run_id"],
            })
        else:
            await broadcast_manager.broadcast({
                "type": "status",
                "protocol": result.get("protocol", "NORMAL"),
                "timestamp": datetime.utcnow().isoformat(),
                "message": None,
            })
```

- [ ] **Step 4: Commit**

```bash
git add backend/agent_orchestrator/broadcast.py backend/agent_orchestrator/main.py
git commit -m "feat: add broadcast SSE manager and /broadcast/stream endpoint"
```

---

## Task 5: Frontend — Auth types + context

**Files:**
- Modify: `frontend/src/types.ts`
- Create: `frontend/src/context/AuthContext.tsx`

- [ ] **Step 1: Add auth types to `frontend/src/types.ts`**

Append to the end of the file:
```typescript
// ── Auth ──────────────────────────────────────────────────────────────────────

export type AdminRole = "SUPER_ADMIN" | "OPERATOR";

export interface User {
  email: string;
  name: string;
  picture: string;
  role: AdminRole;
}

export interface AuthState {
  user: User | null;
  loading: boolean;
  error: string | null;
}
```

- [ ] **Step 2: Install react-router-dom**

```bash
cd frontend
npm install react-router-dom@6
```

- [ ] **Step 3: Create `frontend/src/context/AuthContext.tsx`**

```typescript
import React, { createContext, useContext, useEffect, useState } from "react";
import type { User, AuthState } from "../types";

interface AuthContextValue extends AuthState {
  logout: () => Promise<void>;
  refetch: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  error: null,
  logout: async () => {},
  refetch: async () => {},
});

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ user: null, loading: true, error: null });

  const fetchMe = async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const res = await fetch(`${API_URL}/auth/me`, { credentials: "include" });
      if (res.ok) {
        const user: User = await res.json();
        setState({ user, loading: false, error: null });
      } else {
        setState({ user: null, loading: false, error: null });
      }
    } catch {
      setState({ user: null, loading: false, error: null });
    }
  };

  const logout = async () => {
    await fetch(`${API_URL}/auth/logout`, { method: "POST", credentials: "include" });
    setState({ user: null, loading: false, error: null });
    window.location.href = "/login";
  };

  useEffect(() => { fetchMe(); }, []);

  return (
    <AuthContext.Provider value={{ ...state, logout, refetch: fetchMe }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types.ts frontend/src/context/AuthContext.tsx
git commit -m "feat: add auth types and AuthContext"
```

---

## Task 6: Frontend — Login page

**Files:**
- Create: `frontend/src/pages/LoginPage.tsx`

- [ ] **Step 1: Create `frontend/src/pages/LoginPage.tsx`**

```typescript
import React from "react";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export default function LoginPage() {
  const handleGoogleLogin = () => {
    window.location.href = `${API_URL}/auth/login`;
  };

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="w-full max-w-sm">
        {/* Logo / branding */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-blue-700 mb-4">
            <svg className="w-9 h-9 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">CrowdGuard Command</h1>
          <p className="text-gray-500 text-sm mt-1">Stadium Safety Operations Platform</p>
        </div>

        {/* Login card */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-8 shadow-2xl">
          <h2 className="text-white font-semibold text-lg mb-1">Admin Sign In</h2>
          <p className="text-gray-500 text-sm mb-6">
            Restricted to authorized stadium personnel only.
          </p>

          <button
            onClick={handleGoogleLogin}
            className="w-full flex items-center justify-center gap-3 bg-white hover:bg-gray-100 text-gray-800 font-medium py-3 px-4 rounded-xl transition-colors shadow"
          >
            {/* Google "G" icon */}
            <svg className="w-5 h-5" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Sign in with Google
          </button>

          <p className="text-center text-xs text-gray-600 mt-4">
            Only pre-approved admin emails can access this system.
          </p>
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-gray-700 mt-6">
          CrowdGuard Command · Google Cloud · Agentic Premier League 2026
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/LoginPage.tsx
git commit -m "feat: add Google OAuth login page"
```

---

## Task 7: Frontend — Protected route + App wiring

**Files:**
- Create: `frontend/src/components/ProtectedRoute.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create `frontend/src/components/ProtectedRoute.tsx`**

```typescript
import React from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function ProtectedRoute({ children, requireSuperAdmin = false }: {
  children: React.ReactNode;
  requireSuperAdmin?: boolean;
}) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-gray-500 text-sm animate-pulse">Verifying access...</div>
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;

  if (requireSuperAdmin && user.role !== "SUPER_ADMIN") {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-red-400 text-sm">Access denied — SUPER_ADMIN role required.</div>
      </div>
    );
  }

  return <>{children}</>;
}
```

- [ ] **Step 2: Wrap App.tsx with Router + AuthProvider + ProtectedRoute**

Replace the top of `frontend/src/App.tsx` (imports + export default):
```typescript
import React, { useCallback, useEffect, useRef, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ProtectedRoute } from "./components/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import BroadcastScreen from "./pages/BroadcastScreen";
import { StatusBar } from "./components/StatusBar";
import { StadiumMap } from "./components/StadiumMap";
import { AgentFeed } from "./components/AgentFeed";
import { GateControls } from "./components/GateControls";
import { AlertPanel } from "./components/AlertPanel";
import { useAgentStream } from "./hooks/useAgentStream";
import { getSystemStatus, runOrchestrator, getActiveAlerts, getGates } from "./api";
import type { Alert, Gate, MatchPhase, SystemStatus, Zone } from "./types";
```

Replace the final `export default function App()` with:
```typescript
function Dashboard() {
  // ... (all existing App() content stays here unchanged, just renamed)
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/screen" element={<BroadcastScreen />} />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ProtectedRoute.tsx frontend/src/App.tsx
git commit -m "feat: add protected routes and auth routing"
```

---

## Task 8: Frontend — Broadcast screen

**Files:**
- Create: `frontend/src/hooks/useBroadcast.ts`
- Create: `frontend/src/pages/BroadcastScreen.tsx`

- [ ] **Step 1: Create `frontend/src/hooks/useBroadcast.ts`**

```typescript
import { useEffect, useRef, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface BroadcastEvent {
  type: "emergency" | "status";
  protocol: string;
  timestamp: string;
  message: string | null;
  open_gates?: string[];
  run_id?: string;
}

export function useBroadcast() {
  const [event, setEvent] = useState<BroadcastEvent | null>(null);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const connect = () => {
      const es = new EventSource(`${API_URL}/broadcast/stream`);
      esRef.current = es;

      es.onopen = () => setConnected(true);
      es.onmessage = (e) => {
        try {
          const data: BroadcastEvent = JSON.parse(e.data);
          setEvent(data);
        } catch {}
      };
      es.onerror = () => {
        setConnected(false);
        es.close();
        setTimeout(connect, 3000);
      };
    };

    connect();
    return () => esRef.current?.close();
  }, []);

  return { event, connected };
}
```

- [ ] **Step 2: Create `frontend/src/pages/BroadcastScreen.tsx`**

```typescript
import React, { useEffect, useState } from "react";
import { useBroadcast } from "../hooks/useBroadcast";

const PROTOCOL_CONFIG = {
  EVACUATE: { bg: "bg-red-700", border: "border-red-400", text: "EVACUATE", emoji: "🚨" },
  LOCKDOWN: { bg: "bg-red-900", border: "border-red-300", text: "LOCKDOWN", emoji: "🔒" },
  CAUTION:  { bg: "bg-yellow-700", border: "border-yellow-400", text: "CAUTION", emoji: "⚠️" },
  NORMAL:   { bg: "bg-gray-900", border: "border-gray-700", text: "ALL CLEAR", emoji: "✅" },
};

export default function BroadcastScreen() {
  const { event, connected } = useBroadcast();
  const [flash, setFlash] = useState(false);

  const isEmergency = event?.type === "emergency" &&
    (event.protocol === "EVACUATE" || event.protocol === "LOCKDOWN");

  const config = PROTOCOL_CONFIG[event?.protocol as keyof typeof PROTOCOL_CONFIG]
    ?? PROTOCOL_CONFIG.NORMAL;

  // Flash effect on emergency
  useEffect(() => {
    if (isEmergency) {
      const interval = setInterval(() => setFlash((f) => !f), 800);
      return () => clearInterval(interval);
    }
    setFlash(false);
  }, [isEmergency]);

  return (
    <div className={`min-h-screen flex flex-col items-center justify-center transition-colors duration-500 ${config.bg}`}>

      {/* Connection dot */}
      <div className="absolute top-4 right-4 flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${connected ? "bg-green-400" : "bg-red-400"} animate-pulse`} />
        <span className="text-white text-xs opacity-50">
          {connected ? "Live" : "Reconnecting..."}
        </span>
      </div>

      {/* Normal state — show CrowdGuard branding */}
      {!isEmergency && (
        <div className="text-center">
          <div className="text-8xl mb-6">{config.emoji}</div>
          <h1 className="text-white text-5xl font-bold tracking-widest mb-3">
            {config.text}
          </h1>
          <p className="text-white text-xl opacity-60">CrowdGuard Command · Monitoring Active</p>
          {event?.timestamp && (
            <p className="text-white text-sm opacity-30 mt-4">
              Last update: {new Date(event.timestamp).toLocaleTimeString()}
            </p>
          )}
        </div>
      )}

      {/* Emergency state — full screen alert */}
      {isEmergency && (
        <div className={`text-center px-8 max-w-4xl transition-opacity duration-300 ${flash ? "opacity-100" : "opacity-90"}`}>
          <div className="text-9xl mb-6 animate-bounce">{config.emoji}</div>
          <h1 className="text-white text-6xl font-black tracking-widest mb-6 uppercase">
            {config.text}
          </h1>

          {/* Gemini-generated announcement */}
          {event?.message && (
            <div className={`border-2 ${config.border} rounded-2xl p-6 mb-6 bg-black bg-opacity-30`}>
              <p className="text-white text-2xl font-medium leading-relaxed">
                {event.message}
              </p>
            </div>
          )}

          {/* Open gates */}
          {event?.open_gates && event.open_gates.length > 0 && (
            <div className="flex flex-wrap justify-center gap-3">
              {event.open_gates.map((gate) => (
                <div key={gate}
                  className="bg-green-600 border border-green-400 rounded-lg px-5 py-2 text-white text-lg font-semibold">
                  ✓ {gate.replace(/_/g, " ").toUpperCase()} — OPEN
                </div>
              ))}
            </div>
          )}

          <p className="text-white text-sm opacity-50 mt-8">
            CrowdGuard Command · Follow staff instructions · Stay calm
          </p>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Add `VITE_API_URL` to frontend env example**

```
# frontend/.env.example
VITE_API_URL=http://localhost:8000
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/useBroadcast.ts frontend/src/pages/BroadcastScreen.tsx frontend/.env.example
git commit -m "feat: add stadium broadcast screen and useBroadcast SSE hook"
```

---

## Task 9: User menu in dashboard

**Files:**
- Modify: `frontend/src/components/StatusBar.tsx`

- [ ] **Step 1: Add user avatar + logout to StatusBar**

Import and add to `StatusBar.tsx`:
```typescript
import { useAuth } from "../context/AuthContext";

// Inside StatusBar component, add at the end of the status bar div:
const { user, logout } = useAuth();

// Add this to the right side of the StatusBar JSX:
{user && (
  <div className="flex items-center gap-2 ml-auto">
    {user.picture && (
      <img src={user.picture} alt={user.name}
        className="w-6 h-6 rounded-full border border-gray-700" />
    )}
    <span className="text-xs text-gray-400">{user.name}</span>
    <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-900 text-blue-300 font-medium">
      {user.role}
    </span>
    <button onClick={logout}
      className="text-xs text-gray-600 hover:text-gray-400 transition-colors ml-1">
      Sign out
    </button>
  </div>
)}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/StatusBar.tsx
git commit -m "feat: add user avatar and logout to StatusBar"
```

---

## Self-Review

**Spec coverage:**
- ✅ Google OAuth login page — Task 6
- ✅ Backend OAuth flow + JWT cookie — Tasks 1, 2
- ✅ Role-based access (SUPER_ADMIN / OPERATOR) — Tasks 1, 2, 7
- ✅ Protected routes — Task 7
- ✅ SendGrid email for field_staff + public_pa — Task 3
- ✅ Stadium broadcast screen `/screen` — Task 8
- ✅ SSE broadcast endpoint `/broadcast/stream` — Task 4
- ✅ Broadcast triggered on EVACUATE/LOCKDOWN — Task 4
- ✅ User menu + logout — Task 9
- ✅ `/screen` is unauthenticated (display-only) — Task 8

**No placeholders detected.**

**Type consistency:**
- `User`, `AuthState`, `AdminRole` defined in Task 5, used in Tasks 6, 7, 8, 9
- `BroadcastEvent` defined in Task 8 hook, consumed in Task 8 screen
- Cookie name `cg_session` consistent across Tasks 1, 2, 5
- `API_URL` via `import.meta.env.VITE_API_URL` consistent across Tasks 5, 6, 8
