/**
 * API client for the Deepfake Agentic AI backend.
 * All requests go through NEXT_PUBLIC_API_URL (defaults to http://localhost:8000).
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface DetectionResult {
  request_id: string;
  filename: string;
  file_hash: string;
  is_deepfake: boolean;
  confidence: number;
  label: "REAL" | "FAKE" | "UNCERTAIN";
  processing_time_ms: number;
  artifacts: string[];
  agent_summary: string | null;
}

export interface HealthResult {
  status: string;
  version: string;
  model_loaded: boolean;
  uptime_seconds: number;
}

export interface ReviewCase {
  case_id: string;
  session_id: string;
  kin_token: string;
  legal_name: string;
  device_id: string;
  created_at: string;
  resolved_at: string | null;
  reviewer_id: string | null;
  review_action: string | null;
  notes: string | null;
  status: "pending_review" | "resolved_approved" | "resolved_rejected" | string;
  decision: string;
  agent_recommendation: string;
  dossier_summary: string;
  tool_calls_trace: Array<{
    tool_name: string;
    args: Record<string, any>;
    return_value: Record<string, any>;
    timestamp: string;
    duration_ms: number;
  }>;
  signals: {
    deepfake_score?: number;
    cosine_similarity_score?: number;
    registry_velocity_6hr?: number;
    blink_rate_bpm?: number;
    av_sync_ms?: number;
    webrtc_jitter_ms?: number;
  };
}

export interface ClipAccessResponse {
  session_id: string;
  url: string;
  expires_in: number;
  url_type: string;
  sha256: string;
}

export interface AuditBlock {
  index: number;
  record_hash: string;
  prev_hash: string;
  record_type: string;
  session_id: string;
  timestamp: string;
  payload: Record<string, any>;
}

export interface ChainVerificationResult {
  is_valid: boolean;
  message: string;
  verified_count: number;
  total_count: number;
  block_breakdown: Record<string, number>;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body || res.statusText);
  }
  return res.json() as Promise<T>;
}

/**
 * Upload an image/video file for deepfake detection.
 */
export async function detectDeepfake(file: File): Promise<DetectionResult> {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${BASE_URL}/api/v1/detect`, {
    method: "POST",
    body: form,
  });

  return handleResponse<DetectionResult>(res);
}

/**
 * Fetch backend health status.
 */
export async function getHealth(): Promise<HealthResult> {
  const res = await fetch(`${BASE_URL}/api/v1/health`, {
    cache: "no-store",
  });
  return handleResponse<HealthResult>(res);
}

/**
 * Fetch cases from the review queue with optional status filter.
 * Token is passed securely via X-Reviewer-Token header.
 */
export async function fetchReviewQueue(
  status: string = "pending_review",
  token: string = "",
): Promise<ReviewCase[]> {
  const url = `${BASE_URL}/api/v1/review/queue?status=${encodeURIComponent(status)}`;
  const res = await fetch(url, {
    cache: "no-store",
    headers: {
      "X-Reviewer-Token": token,
    },
  });
  return handleResponse<ReviewCase[]>(res);
}

/**
 * Fetch dossier detail for a specific review case.
 */
export async function fetchReviewCase(
  caseId: string,
  token: string = "",
): Promise<ReviewCase> {
  const res = await fetch(`${BASE_URL}/api/v1/review/queue/${caseId}`, {
    cache: "no-store",
    headers: {
      "X-Reviewer-Token": token,
    },
  });
  return handleResponse<ReviewCase>(res);
}

/**
 * Submit human reviewer decision (approve or reject).
 */
export async function submitReviewDecision(
  caseId: string,
  action: "approve" | "reject",
  reviewerId: string,
  notes?: string,
  token: string = "",
): Promise<any> {
  const res = await fetch(`${BASE_URL}/api/v1/review/queue/${caseId}/decision`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Reviewer-Token": token,
    },
    body: JSON.stringify({
      action,
      reviewer_id: reviewerId,
      notes: notes || "",
    }),
  });
  return handleResponse<any>(res);
}

/**
 * Request a short-lived HMAC-signed streaming URL for an archived video clip.
 * The master reviewer token is passed strictly in the X-Reviewer-Token header.
 */
export async function fetchClipAccess(
  sessionId: string,
  token: string = "",
): Promise<ClipAccessResponse> {
  const res = await fetch(`${BASE_URL}/api/v1/review/${sessionId}/clip`, {
    cache: "no-store",
    headers: {
      "X-Reviewer-Token": token,
    },
  });
  const data = await handleResponse<ClipAccessResponse>(res);
  if (data.url && data.url.startsWith("/")) {
    data.url = `${BASE_URL}${data.url}`;
  }
  return data;
}

/**
 * Fetch all sealed blocks from the cryptographic audit hash chain.
 */
export async function fetchAuditChain(
  token: string = "",
): Promise<AuditBlock[]> {
  const res = await fetch(`${BASE_URL}/api/v1/review/audit-chain`, {
    cache: "no-store",
    headers: {
      "X-Reviewer-Token": token,
    },
  });
  return handleResponse<AuditBlock[]>(res);
}

/**
 * Trigger cryptographic verification of the audit chain.
 */
export async function verifyAuditChain(
  token: string = "",
): Promise<ChainVerificationResult> {
  const res = await fetch(`${BASE_URL}/api/v1/review/audit-chain/verify`, {
    method: "POST",
    headers: {
      "X-Reviewer-Token": token,
    },
  });
  return handleResponse<ChainVerificationResult>(res);
}

/**
 * Submit video clip to /api/v1/liveness/analyze with dynamic challenge validation
 */
export async function analyzeLiveness(
  clip: File | Blob,
  challengeType: string = "general_motion",
  timeoutMs: number = 20000,
): Promise<{
  session_id: string;
  deepfake_score: number;
  challenge_match: boolean;
  blink_rate_bpm: number;
  av_sync_ms: number;
  anomaly_score: number;
  decision: "pass" | "borderline" | "fail" | string;
  video_sha256: string;
}> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const form = new FormData();
    form.append("clip", clip, "liveness.mp4");
    if (challengeType) {
      form.append("challenge_type", challengeType);
    }
    const res = await fetch(`${BASE_URL}/api/v1/liveness/analyze`, {
      method: "POST",
      body: form,
      signal: controller.signal,
    });
    return await handleResponse<any>(res);
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Execute full multi-stage pipeline evaluation
 */
export async function evaluatePipeline(
  payload: {
    kin_token: string;
    legal_name: string;
    device_id: string;
    webrtc_jitter_ms?: number;
    cosine_similarity_score?: number;
    registry_velocity_6hr?: number;
    challenge_match?: boolean;
    deepfake_score?: number;
    blink_rate_bpm?: number;
    av_sync_ms?: number;
  },
  timeoutMs: number = 20000,
): Promise<{
  session_id: string;
  status: "approved" | "rejected" | "escalated_for_review" | string;
  final_decision: "pass" | "borderline" | "fail" | string;
  escalated_to_stage3: boolean;
  reason: string;
}> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${BASE_URL}/api/v1/agent/evaluate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    return await handleResponse<any>(res);
  } finally {
    clearTimeout(timeoutId);
  }
}

