# Deployment & Production Architecture Guide

This guide outlines the production deployment strategy for the **Deepfake Agentic AI** platform:
- **Frontend**: Next.js 16 + React 19 deployed to **Vercel**
- **Backend**: FastAPI + LangGraph ML engine packaged in a production Docker container and deployed to **Render** with persistent disk storage

---

## 1. Architecture Overview & Security Model

```
┌─────────────────────────────────────────────────────────────┐
│                    Vercel Edge Network                      │
│   Next.js 16 App Router (Static & Dynamic Client Hydration) │
│                                                             │
│   Public Variable: NEXT_PUBLIC_API_URL                      │
│   Secret Policy: ZERO client-side secrets / NO tokens baked │
└──────────────────────────────┬──────────────────────────────┘
                               │
            HTTPS REST Requests│ (Strict Pinned CORS)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    Render Cloud Platform                    │
│   Docker Container: Python 3.11-slim + Uvicorn Async Server │
│                                                             │
│   Environment Secrets:                                      │
│     - REVIEWER_TOKEN       (Master header credential)       │
│     - STREAM_SIGNING_KEY   (Independent HMAC secret)        │
│     - OPENAI_API_KEY       (LangGraph LLM synthesis)        │
│                                                             │
│   Persistent Disk (/app/data/storage - 10GB):               │
│     - Raw Wire-Hashed Video Clips (session_id/clip.bin)     │
│     - Append-Only Audit Trail (audit_chain.jsonl)           │
│     - Human Escalation Queue (review_queue.jsonl)           │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Key Security Principles

### A. Zero Client-Side Secret Leakage
- **Eliminated `NEXT_PUBLIC_REVIEWER_TOKEN`**: Next.js statically bakes `NEXT_PUBLIC_*` environment variables directly into client javascript bundles.
- **Interactive Reviewer Authentication Gate**: The Human Review Portal (`/review`) requires manual credential entry, stored exclusively in the browser tab's `sessionStorage`.
- **Session Isolation**: Closing the browser tab destroys the session token.

### B. Short-Lived HMAC Signed Video Stream URLs
- **Log Privacy**: Master credentials (`REVIEWER_TOKEN`) must never appear in query strings (`?token=...`) because URLs are logged in plain text by server proxies, Render access logs, browser history, and HTTP `Referer` headers.
- **Two-Step Stream Access**:
  1. Authenticated client sends `GET /api/v1/review/{session_id}/clip` with `X-Reviewer-Token` header.
  2. Backend returns an ephemeral HMAC-SHA256 signed URL:
     ```
     /api/v1/review/{session_id}/stream?exp=1724330000&sig=5f8d...
     ```
  3. Video element streams directly via the signed URL. The signature expires after 600 seconds and is strictly scoped to `session_id`.

### C. Strict Pinned CORS (Zero Wildcards)
- Origin wildcard (`"*"`) is strictly disallowed.
- Accepted origins:
  - Local development: `http://localhost:3000`, `http://127.0.0.1:3000`
  - Explicit production domain: `FRONTEND_URL` / `ALLOWED_ORIGINS`
  - Vercel Preview Deployments: regex matching `r"^https:\/\/.*\.vercel\.app$"`

---

## 3. Backend Deployment on Render

### Option A: Deploy via Blueprint (`render.yaml`) [Recommended]

1. Push your repository to GitHub or GitLab.
2. In the Render Dashboard, select **New +** → **Blueprint**.
3. Connect your repository. Render will automatically detect `backend/render.yaml`.
4. Render provisions:
   - Docker Web Service (`deepfake-agentic-ai-backend`)
   - 10 GB Persistent Disk mounted at `/app/data/storage`
   - Auto-generated cryptographically secure `REVIEWER_TOKEN` and `STREAM_SIGNING_KEY`
5. Fill in the remaining secret environment variables:
   - `OPENAI_API_KEY`: Your OpenAI API key (for LangGraph natural language synthesis).
   - `FRONTEND_URL`: Your Vercel production URL (e.g. `https://deepfake-agentic-ai.vercel.app`).
6. Deploy!

### Option B: Manual Web Service Setup

1. In Render Dashboard, click **New +** → **Web Service**.
2. Source: Connect repository, Root Directory: `backend`.
3. Runtime: **Docker**, Dockerfile Path: `./Dockerfile`.
4. Add Persistent Disk:
   - Name: `clips-storage`
   - Mount Path: `/app/data/storage`
   - Size: `10 GB`
5. Configure Environment Variables:
   ```bash
   ENVIRONMENT=production
   LOG_LEVEL=INFO
   ALLOWED_ORIGINS=https://deepfake-agentic-ai.vercel.app
   VERCEL_PREVIEW_REGEX=^https:\/\/.*\.vercel\.app$
   STORAGE_BACKEND=local
   STORAGE_LOCAL_ROOT=/app/data/storage
   REVIEWER_TOKEN=<generate-strong-random-token>
   STREAM_SIGNING_KEY=<generate-strong-signing-key>
   REVIEW_URL_EXPIRY_SECONDS=600
   OPENAI_API_KEY=sk-...
   ```

---

## 4. Frontend Deployment on Vercel

1. Import your project repository in the **Vercel Dashboard**.
2. Set **Root Directory** to `frontend`.
3. Framework Preset: **Next.js**.
4. Configure Environment Variables:
   ```bash
   NEXT_PUBLIC_API_URL=https://<your-render-service-name>.onrender.com
   ```
5. Click **Deploy**. Vercel will build the Next.js application using Turbopack and configure security headers from `vercel.json`.

---

## 5. Pre-Launch Verification & CORS Testing

Run these verification commands against your deployed backend:

### 1. Health Check Probes
```bash
# Public liveness check
curl -I https://<your-backend>.onrender.com/health
# Expected: HTTP/1.1 200 OK

# Detailed model health check
curl -s https://<your-backend>.onrender.com/api/v1/health | jq .
# Expected: {"status": "ok", "version": "0.1.0", "model_loaded": true, ...}
```

### 2. Positive CORS Verification (Allowed Origin)
```bash
curl -I -X OPTIONS https://<your-backend>.onrender.com/api/v1/health \
  -H "Origin: https://deepfake-agentic-ai.vercel.app" \
  -H "Access-Control-Request-Method: GET"

# Expected Headers:
# Access-Control-Allow-Origin: https://deepfake-agentic-ai.vercel.app
# Access-Control-Allow-Credentials: true
```

### 3. Negative CORS Verification (Malicious Origin Rejection)
```bash
curl -I -X OPTIONS https://<your-backend>.onrender.com/api/v1/health \
  -H "Origin: https://malicious-attacker.com" \
  -H "Access-Control-Request-Method: GET"

# Expected: Access-Control-Allow-Origin header is ABSENT in response
```

### 4. Reviewer Header Auth & Ephemeral Signed Stream
```bash
# Fetch short-lived signed video URL
curl -s https://<your-backend>.onrender.com/api/v1/review/<session_id>/clip \
  -H "X-Reviewer-Token: <your-reviewer-token>" | jq .

# Expected:
# {
#   "session_id": "...",
#   "url": "/api/v1/review/.../stream?exp=1724...&sig=...",
#   "expires_in": 600,
#   "url_type": "internal_stream",
#   "sha256": "..."
# }

# Access stream with valid signed URL
curl -I "https://<your-backend>.onrender.com/api/v1/review/<session_id>/stream?exp=...&sig=..."
# Expected: HTTP/1.1 200 OK (Content-Type: video/mp4)

# Access stream with tampered/expired signature
curl -I "https://<your-backend>.onrender.com/api/v1/review/<session_id>/stream?exp=1000&sig=invalid"
# Expected: HTTP/1.1 403 Forbidden
```

---

## 6. Alternative Deployment Targets (Reference Architectures)

| Cloud Target | Pros | Storage Strategy | Config Reference |
| :--- | :--- | :--- | :--- |
| **Render** (Primary) | Simple persistent disk, native Docker, Blueprint IaC | `/app/data/storage` volume disk | `render.yaml` |
| **Fly.io** | Low latency edge deployment, fast container starts | `fly volumes create storage_vol` | `fly.toml` with mounts |
| **Railway** | Native Docker, persistent volume plugins | Railway volume `/app/data/storage` | `railway.json` |
| **Hugging Face Spaces** | Free GPU/CPU tiers for ML models | Persistent Storage tier or MinIO/R2 backend | `Dockerfile` (Spaces SDK: docker) |
