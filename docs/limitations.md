# System Limitations & Future Work

This document outlines the current operational boundaries, architectural trade-offs, and scheduled future work for the **Deepfake Agentic AI** platform.

---

## 1. Implemented Features (Operational)

### Unified Cryptographic Hash Chain (`audit_chain.jsonl`)
- **Implemented**: All upload events, liveness decision events, and reviewer clip access events are interleaved into a single, append-only cryptographic hash chain.
- **Tamper Evidence**: Each entry contains `prev_hash` pointing to the previous block's SHA-256 digest, and canonical JSON serialization guarantees deterministic validation across all `record_type` values (`upload`, `decision`, `access`).
- **No Split-Brain Audit Trails**: The frontend never accesses storage directly; all reviewer clip retrievals flow through backend-mediated endpoints (`GET /api/v1/review/{session_id}/clip`) and are sealed in the same chain as detection decisions.

### Immediate Wire-Byte Hashing & Decoupled Storage Archival
- **Implemented**: Raw bytes are hashed (`video_sha256`) immediately upon arrival over the wire, before any decoding, transcoding, frame extraction, or subsampling.
- **Resilience**: Storage write (`storage.write(...)`) occurs before scoring starts. If the scoring pipeline crashes or throws an exception, the clip remains archived and verified in storage with the exact SHA-256 digest.

---

## 2. Current System Limitations & Gaps

### A. Retention & Deletion Automation
- **Status**: Declared in `backend/app/core/retention_policy.yaml` (`retention_years: 7`), but **automated lifecycle deletion is NOT implemented**.
- **Scope**: Under regulatory compliance rules, the 7-year retention policy covers the entire chain of custody: the raw media clips (`storage`), the review queue case records (`review_queue.jsonl`), and the append-only cryptographic audit trail (`audit_chain.jsonl`).
- **Impact**: Clips, cases, and audit blocks remain stored indefinitely unless manually purged.
- **Future Roadmap**:
  - Integrate S3/MinIO Information Lifecycle Management (ILM) policies and Cloudflare R2 bucket lifecycle rules.
  - Implement automated expiry triggers (`expiry_date`) with grace periods.
  - Automate legal hold enforcement (`legal_hold: true`) to prevent automated deletion during active investigations or litigation.

### B. Encryption-at-Rest Key Management / KMS Strategy
- **Status**: Object storage currently relies on underlying filesystem / cloud provider default storage encryption. Dedicated per-session envelope encryption is **NOT implemented**.
- **Future Roadmap**:
  - Implement envelope encryption (AES-256-GCM) with AWS KMS, Cloudflare Key Management, or HashiCorp Vault.
  - Per-session Data Encryption Keys (DEKs) wrapped by a Customer Master Key (CMK).
  - Enforce 90-day automated CMK key rotation and cryptographically enforce access policies.

### C. Automated Alerting & Telemetry on Chain Verification Failures
- **Status**: The verification tool (`verify_audit_chain.py` and `verify_chain()`) detects any broken hash link or modified payload, but verification is executed on-demand / in CI.
- **Future Roadmap**:
  - Implement periodic background validation jobs (e.g. cron daemon) that continuously audit the chain.
  - Wire automated webhook / PagerDuty / Sentry alerts if a hash mismatch or sequence break is ever detected.

### D. External Timestamping & Asymmetric HSM Signing
- **Status**: Timestamps are generated in UTC ISO-8601 from the server clock. Blocks are hashed using SHA-256 without external digital signatures.
- **Future Roadmap**:
  - Integrate RFC 3161 compliant external Time Stamping Authorities (TSA) to provide legally irrefutable proof-of-time.
  - Implement Hardware Security Module (HSM) / asymmetric key signing for periodic chain checkpoint anchors.

### E. Storage Bucket ACLs & Frontend Isolation
- **Status**: The backend operates as the sole service principal. Frontend clients never receive storage bucket credentials.
- **Operational Requirement**: When deploying to production MinIO or Cloudflare R2, bucket policies MUST be configured to explicitly `DENY *` from public internet and permit access only to the backend IAM credentials / API tokens.

### F. Reviewer Authentication & Session Token Lifecycle
- **Status**: Reviewer access relies on a shared `REVIEWER_TOKEN` stored dynamically in the browser's `sessionStorage` (never in code bundles or persistent localStorage).
- **Stream URL Security**: Video streams use ephemeral HMAC-SHA256 signatures (`exp` timestamp + `sig` digest) generated on-demand via `GET /api/v1/review/{session_id}/clip` with 5–10 minute expiry, preventing durable master credentials from leaking into server access logs, browser history, or `Referer` headers.
- **Trade-off & Limitations**:
  - The shared token does not provide individual cryptographic identity or multi-factor authentication (MFA).
  - Browser tab closure clears `sessionStorage`, requiring re-authentication.
- **Future Roadmap**:
  - Integrate Enterprise Identity Provider (IdP) via OAuth 2.0 / OpenID Connect (OIDC) / SAML 2.0 (e.g. Okta, Auth0, Microsoft Entra ID).
  - Implement per-reviewer JSON Web Tokens (JWT) with fine-grained RBAC roles (`tier1_reviewer`, `compliance_auditor`, `admin`).
  - Deploy WebAuthn / FIDO2 hardware security keys for Stage 4 biometric adjudication.

