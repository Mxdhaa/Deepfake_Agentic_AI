# Deepfake Agentic AI — Enterprise Biometric KYC & Liveness System 🔍🛡️

> **Enterprise-Grade Deepfake Detection & Physiological Liveness KYC Pipeline**  
> Powered by **LangGraph Multi-Agent Orchestration**, **Contiguous Optical Flow Gesture Tracking**, **Neural Artifact Scoring**, **MTCNN-Aligned Biometric Face Matching**, and **EasyOCR Document Analysis**.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green.svg)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.1.9-purple.svg)](https://langchain-ai.github.io/langgraph/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.9-red.svg)](https://opencv.org/)

---

## 📌 Executive Summary

Modern Identity Verification (KYC) systems are increasingly vulnerable to AI-generated deepfakes, video replay attacks, and digital face-swaps. **Deepfake Agentic AI** provides a 4-step autonomous verification pipeline that combines real-time physiological liveness challenges, deepfake neural artifact detection, and biometric face verification within a tamper-evident audit ledger.

---

## 🏛️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                   NEXT.JS FRONTEND (Port 3000)                          │
│   Step 1: User Info & OTP  │  Step 2: ID Document Upload  │  Step 3: Liveness & Video  │
└───────────────────────────────────────────┬─────────────────────────────────────────────┘
                                            │ REST API (JSON / Multipart)
                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                FASTAPI BACKEND SERVER (Port 8000)                       │
│                                                                                         │
│  ┌───────────────────────┐   ┌───────────────────────────┐   ┌───────────────────────┐  │
│  │ 1. EasyOCR Service    │   │ 2. Biometric Matcher      │   │ 3. Deepfake Detector  │  │
│  │    Document Text      │   │    MTCNN Aligned Face     │   │    PyTorch Neural     │  │
│  │    Extraction & OCR   │   │    Inception-ResNet Similarity│   │    Artifact Scoring   │  │
│  └───────────────────────┘   └───────────────────────────┘   └───────────────────────┘  │
│                                                                                         │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │ 4. Optical Flow Sequential Liveness Engine                                        │  │
│  │    - Contiguous 30fps Video Decoding (bytes_to_frames_contiguous)                │  │
│  │    - OpenCV Farneback Optical Flow Vector Estimation & Face ROI Tracking          │  │
│  │    - 2-Stage Excursion Accumulator (accum_mag >= 0.38, sustain_count >= 2)         │  │
│  │    - Strict Physical Rebound Sequence Validator (_validate_physical_challenge)   │  │
│  └───────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │ 5. LangGraph Multi-Agent Orchestration & Tamper-Evident Audit Ledger              │  │
│  │    - Deterministic Signal Collection (10 Biometric/OCR/Liveness Signals)          │  │
│  │    - Automated Retry Routing for Borderline Signals                               │  │
│  │    - SHA-256 Hash-Chained Audit Seal (app.services.audit)                         │  │
│  └───────────────────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🔬 Methodology & Technical Deep-Dive

### 1. Contiguous Optical Flow Liveness Challenge Engine
The liveness challenge issues a dynamic 3-gesture sequence (e.g., `['down', 'right', 'down']` or `['up', 'down', 'right']`).

* **Contiguous 30fps Frame Decoding (`video.py`)**: Decoding extracts 150 consecutive 30fps video frames without sparse seeking gaps, ensuring smooth temporal motion continuity.
* **Farneback Optical Flow & Face ROI Tracking (`liveness.py`)**: Computes dense velocity vectors $(dx, dy)$ combining 70% face crop optical flow and 30% face center bounding box displacement.
* **Two-Stage Motion Accumulator**:
  - *Stage 1 (Excursion Candidate)*: Evaluates candidate direction (`dir_cand`) against thresholds (`turn_dx_min = 0.28`, `nod_dy_min = 0.32`).
  - *Stage 2 (Sustained Energy Gate)*: Promotes candidates to gesture peaks only when sustained continuously over time (`accum_mag >= 0.38` AND `sustain_count >= 2` or `accum_mag >= 0.70`).
* **Strict Physical Rebound Sequence Validation**:
  - Enforces that Gesture 1 MUST be the initial gesture performed (`detected[0] == expected[0]`).
  - Tracks expected return-to-center rebound strokes (`OPPOSITE_DIR`: `up` after `down`, `left` after `right`).
  - Strips natural posture rebounds while **immediately rejecting** unassigned perpendicular gestures or video replay attempts (e.g., looking in all 4 directions).

### 2. Deepfake Neural Artifact Scoring
Uses a PyTorch neural checkpoint combined with frequency-domain heuristics (Laplacian variance blur check, FFT high-frequency ratio, and chroma distribution penalty) to generate a deepfake score between `0.0` (Real) and `1.0` (Fake).

### 3. MTCNN-Aligned Biometric Face Matching
Extracts face crops from both the uploaded government ID document and live camera frames. Aligns facial landmarks and computes cosine similarity (pass threshold $\ge 0.55$).

### 4. LangGraph Multi-Agent Orchestration & SHA-256 Audit Trail
Aggregates 10 identity verification signals. Borderline scores trigger an automated retry loop; hard failures route to human reviewer escalation. Every state transition is cryptographically sealed in a SHA-256 hash chain.

---

## 📁 Repository Structure

```
Deepfake_Agentic_AI/
├── backend/                        ← Python FastAPI Backend & Detection Services
│   ├── main.py                     ← FastAPI Server Entrypoint
│   ├── requirements.txt            ← Pinned Python Dependencies
│   └── app/
│       ├── api/                    ← REST API Routes (/verification, /liveness, /health)
│       ├── agents/                 ← LangGraph Verification Agent State Machine
│       ├── services/
│       │   ├── liveness.py         ← Optical Flow Gesture & Liveness Engine
│       │   ├── verification_service.py ← End-to-End KYC Flow & Clip Archival
│       │   ├── video.py            ← Contiguous Video Frame Decoder
│       │   ├── ocr_service.py      ← EasyOCR Document Text Extractor
│       │   └── audit.py            ← SHA-256 Hash-Chained Audit Ledger
│       ├── models/                 ← Deepfake Neural Artifact Detector
│       └── core/                   ← Configuration YAML & Pydantic Settings
│
├── frontend/                       ← Next.js 14 Web Application
│   ├── app/onboarding/             ← 4-Step Interactive Verification Flow
│   ├── components/                 ← Web Camera Capture & Verification Breakdown UI
│   └── lib/api.ts                  ← API Integration Client
│
├── data/
│   ├── storage/                    ← Verification Session Records & Video Archives
│   └── samples/                    ← Test Document & Face Media Samples
│
└── models/                         ← PyTorch Neural Weights (detector.pth)
```

---

## 🚀 Local Quick Start & Running Instructions

### Prerequisites
* **Python**: 3.11+
* **Node.js**: 20+
* **Git**: Installed

---

### 1. Clone the Repository
```bash
git clone https://github.com/Mxdhaa/Deepfake_Agentic_AI.git
cd Deepfake_Agentic_AI
```

---

### 2. Start Backend Server (FastAPI)

```bash
cd backend
python -m venv .venv

# Activate Virtual Environment:
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

# Install Dependencies
pip install -r requirements.txt

# Start Backend Server on Port 8000
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```
* **API Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Backend Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

### 3. Start Frontend Server (Next.js)

Open a second terminal window:

```bash
cd frontend
npm install
npm run dev
```
* **KYC Application UI**: [http://localhost:3000/onboarding](http://localhost:3000/onboarding)

---

## 🌐 Deploying to GitHub & Production

### 1. Push Code to GitHub

```bash
git add .
git commit -m "feat(kyc): add Enterprise Deepfake & Liveness Verification Pipeline"
git branch -M master
git remote add origin https://github.com/Mxdhaa/Deepfake_Agentic_AI.git
git push -u origin master
```

---

### 2. Production Deployment Options

#### Option A: Render / Railway Deployment (Backend)
1. Connect your GitHub repository to **Render** or **Railway**.
2. Set Build Command: `pip install -r backend/requirements.txt`
3. Set Start Command: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Set Environment Variables: `PYTHON_VERSION=3.11.0`

#### Option B: Vercel Deployment (Frontend)
1. Import your GitHub repository into **Vercel**.
2. Set Root Directory: `frontend`
3. Add Environment Variable: `NEXT_PUBLIC_API_URL=https://your-backend-api.onrender.com`
4. Deploy!

#### Option C: Docker Container Deployment
```bash
# Build & Run Backend Container
docker build -t deepfake-backend backend/
docker run -d -p 8000:8000 deepfake-backend
```

---

## 📊 Verification Decision Breakdown

| Signal Category | Signal Name | Pass Condition |
| :--- | :--- | :--- |
| **Identity & OCR** | Identity Record | Exact CKYC Database Match |
| **Identity & OCR** | Legal Name & DOB | Match Score $\ge 70\%$ |
| **Security** | Phone OTP | Cryptographically Verified |
| **Document** | Authenticity & Face | Valid ID Crop Extracted |
| **Biometrics** | Live Face Match | Cosine Similarity $\ge 0.55$ |
| **Physiology** | Liveness Challenge | Strict Physical Gesture Sequence Match |
| **AI Defense** | Deepfake Analysis | Neural Anomaly Score $< 0.40$ (NO_ANOMALY) |

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

---

> **Built for the Deepfake Agentic AI Research Project**  
> Maintained by [Mxdhaa](https://github.com/Mxdhaa)
