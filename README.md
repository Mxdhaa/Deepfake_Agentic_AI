# Deepfake Agentic AI 🔍🤖

> **LangGraph-powered deepfake detection system** — upload an image or video and receive a structured, explainable analysis report powered by a multi-step AI agent pipeline.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green.svg)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.1.9-purple.svg)](https://langchain-ai.github.io/langgraph/)

---

## Architecture

```
┌─────────────────┐        REST API        ┌─────────────────────────────────┐
│  Next.js 14     │ ─────────────────────▶ │  FastAPI + LangGraph Agent      │
│  App Router     │ ◀───────────────────── │                                 │
│  Vercel Deploy  │    JSON DetectionResult │  preprocess → detect →          │
└─────────────────┘                        │  analyze → report               │
                                           │                                 │
                                           │  EfficientNet-B4 / ViT-B/16     │
                                           │  structlog JSON logging          │
                                           └─────────────────────────────────┘
```

## Project Structure

```
Deepfake_Agentic_AI/
├── backend/               ← Python FastAPI + LangGraph detection pipeline
│   ├── main.py            ← App entry point (uvicorn)
│   ├── requirements.txt   ← Pinned Python dependencies
│   ├── .env.example       ← Copy to .env and fill in your values
│   └── app/
│       ├── api/routes.py  ← REST endpoints (/detect, /health)
│       ├── agent/graph.py ← LangGraph 4-node detection state machine
│       ├── models/        ← Detector model class (EfficientNet stub)
│       ├── utils/         ← Structured logging (structlog)
│       └── core/config.py ← Pydantic settings
│
├── frontend/              ← Next.js 14 App Router (TypeScript + Tailwind)
│   ├── app/               ← Pages: / (upload), /results, /dashboard
│   └── components/        ← Reusable UI components
│
├── data/
│   ├── samples/real/      ← Test images (real faces) ← committed
│   ├── samples/fake/      ← Test images (deepfakes)  ← committed
│   └── raw/               ← Full datasets (gitignored — download via scripts)
│
├── docs/
│   └── architecture.md    ← Detailed architecture + component diagram
│
└── scripts/
    ├── download_datasets.sh  ← FaceForensics++, DFDC, Celeb-DF v2
    ├── gen_synthetic.py      ← Synthetic augmentation (blend/warp/color)
    └── eval.py               ← Model evaluation (AUC, F1, EER, latency)
```

## Quick Start

### Backend (Python 3.11+)

```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # Fill in your values

uvicorn main:app --reload --port 8000
# → API docs: http://localhost:8000/docs
# → Health:   http://localhost:8000/health
```

### Frontend (Node 20+)

```bash
cd frontend
npm install
cp .env.local.example .env.local

npm run dev
# → http://localhost:3000
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/detect` | Upload image/video → detection result |
| `GET`  | `/api/v1/health` | Detailed health + model status |
| `GET`  | `/health` | Quick liveness probe |
| `GET`  | `/docs` | Swagger UI |

**Example request:**
```bash
curl -X POST http://localhost:8000/api/v1/detect \
  -F "file=@my_image.jpg" | python -m json.tool
```

**Example response:**
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "filename": "my_image.jpg",
  "file_hash": "a3f5b9c2...",
  "is_deepfake": true,
  "confidence": 0.847,
  "label": "FAKE",
  "processing_time_ms": 142.3,
  "artifacts": ["inconsistent_facial_texture", "frequency_domain_anomaly"],
  "agent_summary": "Analysis complete. The media was classified as FAKE with 84.7% deepfake probability."
}
```

## Detection Pipeline (LangGraph)

```
[preprocess] ──▶ [detect] ──▶ [analyze] ──▶ [report] ──▶ END
     │               │              │              │
  PIL/OpenCV    EfficientNet    Heuristic      JSON
  decode+resize  B4 / ViT      Artifacts    Response
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Tailwind CSS |
| Backend | FastAPI, uvicorn, pydantic-settings |
| AI Agent | LangGraph, LangChain |
| Detection | EfficientNet-B4 / ViT-B/16 (PyTorch) |
| Vision | OpenCV, Pillow |
| Logging | structlog (JSON in prod, pretty in dev) |
| Deploy FE | Vercel |

## Dataset Downloads

```bash
bash scripts/download_datasets.sh ff++    # FaceForensics++ (needs access)
bash scripts/download_datasets.sh dfdc    # DFDC (Meta AI)
bash scripts/download_datasets.sh celebdf # Celeb-DF v2
```

## Model Evaluation

```bash
cd backend
python ../scripts/eval.py \
  --model models/detector.pth \
  --data  ../data/samples/ \
  --output ../docs/eval_results.json
```

## License

MIT — see [LICENSE](LICENSE)

---

> Built for the Deepfake Agentic AI research project.  
> Phase 0: Environment Setup | Phase 1: Core Detection | Phase 2: Full Agent | Phase 3: Evaluation
