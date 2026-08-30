/**
 * API client for the Deepfake Agentic AI backend.
 * In browser production on Vercel, BASE_URL is strictly "" (relative same-origin)
 * so all requests route through Next.js server-side rewrites, completely bypassing
 * browser CORS and Cloudflare bot challenge blocks.
 */
const getBaseUrl = (): string => {
  if (typeof window !== "undefined") {
    // In local development on localhost / 127.0.0.1
    if (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") {
      return process.env.NEXT_PUBLIC_API_URL ? process.env.NEXT_PUBLIC_API_URL.replace(/\/+$/, "") : "http://localhost:8000";
    }
    // In browser production on Vercel: ALWAYS use relative path ""
    return "";
  }
  return (process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "https://deepfake-agentic-ai-backend.onrender.com").replace(/\/+$/, "");
};

export const BASE_URL = getBaseUrl();

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

export async function safeFetch(url: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(url, init);
  } catch (err: any) {
    if (err instanceof ApiError) throw err;
    const targetUrl = url.startsWith("http")
      ? url
      : `${typeof window !== "undefined" ? window.location.origin : ""}${url}`;
    throw new ApiError(0, `Cannot reach backend proxy (${targetUrl}). Please verify the server is active and try again.`);
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    let parsedMessage = body || res.statusText;
    try {
      const parsed = JSON.parse(body);
      if (parsed && typeof parsed === "object") {
        if (parsed.message) {
          parsedMessage = parsed.message;
        } else if (parsed.detail) {
          if (typeof parsed.detail === "object") {
            parsedMessage = parsed.detail.message || parsed.detail.error || JSON.stringify(parsed.detail);
          } else {
            parsedMessage = parsed.detail;
          }
        } else if (parsed.error) {
          parsedMessage = parsed.error;
        }
      }
    } catch {}
    throw new ApiError(res.status, parsedMessage);
  }
  return res.json() as Promise<T>;
}

/**
 * Upload an image/video file for deepfake detection.
 */
export async function detectDeepfake(file: File): Promise<DetectionResult> {
  const form = new FormData();
  form.append("file", file);

  const res = await safeFetch(`${BASE_URL}/api/v1/detect`, {
    method: "POST",
    body: form,
  });

  return handleResponse<DetectionResult>(res);
}

/**
 * Fetch backend health status.
 */
export async function getHealth(): Promise<HealthResult> {
  const res = await safeFetch(`${BASE_URL}/api/v1/health`, {
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
  const res = await safeFetch(url, {
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
  const res = await safeFetch(`${BASE_URL}/api/v1/review/queue/${caseId}`, {
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
  const res = await safeFetch(`${BASE_URL}/api/v1/review/queue/${caseId}/decision`, {
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
  const res = await safeFetch(`${BASE_URL}/api/v1/review/${sessionId}/clip`, {
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
  const res = await safeFetch(`${BASE_URL}/api/v1/review/audit-chain`, {
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
  const res = await safeFetch(`${BASE_URL}/api/v1/review/audit-chain/verify`, {
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
    const res = await safeFetch(`${BASE_URL}/api/v1/liveness/analyze`, {
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
    const res = await safeFetch(`${BASE_URL}/api/v1/agent/evaluate`, {
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

// ─── Stateful Verification Architecture Contracts (Refactored) ─────────────────

export interface DecisionTable {
  identity_record: "MATCH" | "NO_MATCH" | "NOT_ATTEMPTED";
  name: "MATCH" | "NO_MATCH" | "NOT_ATTEMPTED";
  dob: "MATCH" | "NO_MATCH" | "NOT_ATTEMPTED";
  ckyc_number: "MATCH" | "NO_MATCH" | "NOT_ATTEMPTED";
  phone_otp: "VERIFIED" | "FAILED" | "NOT_ATTEMPTED";
  document: "MATCH" | "NO_MATCH" | "NOT_ATTEMPTED";
  document_face: "MATCH" | "NO_MATCH" | "NOT_ATTEMPTED";
  live_face: "MATCH" | "UNCERTAIN" | "NO_MATCH" | "NOT_ATTEMPTED";
  liveness: "CONFIRMED" | "UNCERTAIN" | "FAILED" | "NOT_ATTEMPTED";
  deepfake_analysis: "NO_ANOMALY" | "FLAGGED" | "NOT_ATTEMPTED";
}

export interface VerificationSessionState {
  referenceId: string;
  ckycNumber: string;
  legalName: string;
  status: "IN_PROGRESS" | "UNDER_REVIEW" | "VERIFIED" | "NOT_VERIFIED" | "ALREADY_VERIFIED";
  createdAt: string;
  updatedAt: string;
  phoneVerified: boolean;
  documentMatch: boolean;
  faceMatch: string;
  livenessResult: string;
  deepfakeResult: string;
  finalDecision?: string | null;
  finalReason?: string | null;
  decisionTable: DecisionTable;
  documentDetails?: any;
  detectionMode?: string;
  challengeSequence?: string[];
  retryCount?: number;
  retryRequested?: boolean;
  retryNote?: string | null;
  agentReasoningTrace?: any;
}

/**
 * 1. Start Verification with CKYC Registry Match & Already-Verified Shortcut
 */
export async function startVerification(payload: {
  legalName: string;
  dateOfBirth: string;
  ckycNumber: string;
}): Promise<{
  referenceId: string;
  status: "IN_PROGRESS" | "ALREADY_VERIFIED" | string;
  message?: string;
  maskedPhone?: string;
  stages_completed?: string[];
  challengeSequence?: string[];
}> {
  const res = await safeFetch(`${BASE_URL}/api/v1/verification/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return handleResponse<any>(res);
}

/**
 * 2. Get full state of session by referenceId (used on page refresh/reconstruct)
 */
export async function getVerificationStatus(referenceId: string): Promise<VerificationSessionState> {
  const res = await safeFetch(`${BASE_URL}/api/v1/verification/${referenceId}/status`, {
    cache: "no-store",
  });
  return handleResponse<VerificationSessionState>(res);
}

/**
 * 3. Lookup active session by CKYC Number
 */
export async function lookupVerificationByCkyc(ckycNumber: string): Promise<{
  ckycNumber: string;
  legalName: string;
  registryStatus: string;
  referenceId?: string | null;
  sessionStatus?: string;
}> {
  const res = await safeFetch(`${BASE_URL}/api/v1/verification/lookup?ckycNumber=${encodeURIComponent(ckycNumber)}`, {
    cache: "no-store",
  });
  return handleResponse<any>(res);
}

/**
 * 4. Send Phone OTP
 */
export async function sendVerificationOtp(referenceId: string): Promise<{
  sent: boolean;
  maskedPhone: string;
  demoOtp?: string;
  expiresInSeconds: number;
}> {
  const res = await safeFetch(`${BASE_URL}/api/v1/verification/${referenceId}/otp/send`, {
    method: "POST",
  });
  return handleResponse<any>(res);
}

/**
 * 5. Verify Phone OTP
 */
export async function verifyVerificationOtp(referenceId: string, otp: string): Promise<{
  verified: boolean;
  status: string;
  remainingAttempts: number;
  message?: string;
}> {
  const res = await safeFetch(`${BASE_URL}/api/v1/verification/${referenceId}/otp/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ otp }),
  });
  return handleResponse<any>(res);
}

/**
 * Client-side image normalization: only downscales extremely large images (>2000px).
 * Uses high quality (0.97) to preserve small portrait details on Aadhaar / ID cards.
 * The Vercel proxy proxies server-to-server so payload size limits are not a concern.
 */
async function compressImageForUpload(file: File | Blob, maxDim = 2000, quality = 0.97): Promise<Blob> {
  if (typeof window === "undefined" || !(file instanceof Blob)) {
    return file;
  }
  if (!file.type || !file.type.startsWith("image/")) {
    return file;
  }
  return new Promise((resolve) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      let { width, height } = img;
      if (width > maxDim || height > maxDim) {
        if (width > height) {
          height = Math.round((height * maxDim) / width);
          width = maxDim;
        } else {
          width = Math.round((width * maxDim) / height);
          height = maxDim;
        }
      }
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        resolve(file);
        return;
      }
      ctx.drawImage(img, 0, 0, width, height);
      canvas.toBlob(
        (blob) => resolve(blob || file),
        "image/jpeg",
        quality
      );
    };
    img.onerror = () => resolve(file);
    img.src = url;
  });
}

/**
 * 6. Upload ID Document with OCR Cross-Check
 */
export async function uploadVerificationDocument(
  referenceId: string,
  documentFile: File | Blob,
): Promise<{
  referenceId: string;
  documentMatch: boolean;
  extractedFields: any;
  fieldChecks: { name: string; dob: string; ckyc: string };
  message: string;
}> {
  const compressed = await compressImageForUpload(documentFile);
  const form = new FormData();
  const filename = (documentFile instanceof File && documentFile.name) ? documentFile.name.replace(/\.[^/.]+$/, ".jpg") : "id_document.jpg";
  form.append("document", compressed, filename);
  const res = await safeFetch(`${BASE_URL}/api/v1/verification/${referenceId}/document`, {
    method: "POST",
    body: form,
  });
  return handleResponse<any>(res);
}

/**
 * 7. Submit Live Camera Capture & 1:1 Face Match
 */
export async function submitVerificationLiveness(
  referenceId: string,
  clip: File | Blob,
  challengeType?: string,
): Promise<{
  referenceId: string;
  faceMatch: "MATCH" | "NO_MATCH";
  faceSimilarityScore: number;
  livenessResult: "CONFIRMED" | "UNCERTAIN" | "FAILED";
  deepfakeResult: "NO_ANOMALY" | "FLAGGED";
  deepfakeScore: number;
  challengeMatch: boolean;
  detectedSequence?: string[];
  expectedSequence?: string[];
  message: string;
}> {
  const form = new FormData();
  form.append("clip", clip, "liveness.mp4");
  if (challengeType) {
    form.append("challenge_type", challengeType);
  }
  const res = await safeFetch(`${BASE_URL}/api/v1/verification/${referenceId}/liveness`, {
    method: "POST",
    body: form,
  });
  return handleResponse<any>(res);
}

/**
 * 8. Finalize Verification & Aggregate 10-Signal Decision
 */
export async function finalizeVerification(referenceId: string): Promise<{
  referenceId: string;
  ckycNumber: string;
  legalName: string;
  status: "VERIFIED" | "UNDER_REVIEW" | "NOT_VERIFIED";
  finalDecision: string;
  finalReason: string;
  decisionTable: DecisionTable;
  verifiedAt?: string;
  retryRequested?: boolean;
  retryCount?: number;
  retryNote?: string | null;
  challengeSequence?: string[];
  agentReasoningTrace?: any;
}> {
  const res = await safeFetch(`${BASE_URL}/api/v1/verification/${referenceId}/finalize`, {
    method: "POST",
  });
  return handleResponse<any>(res);
}

/**
 * 9. Submit direct reviewer decision on a session by referenceId
 */
export async function submitSessionReviewDecision(
  referenceId: string,
  action: "approve" | "reject",
  reviewerId: string,
  notes?: string,
  token: string = "",
): Promise<any> {
  const res = await safeFetch(`${BASE_URL}/api/v1/review/${referenceId}/decision`, {
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
