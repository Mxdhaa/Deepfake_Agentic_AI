import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Identity Reconstruction — CKYC & Biometric Liveness",
  description:
    "Next-generation identity verification powered by physiological signal analysis, cryptographic hash chaining, and autonomous liveness verification.",
  keywords: ["identity verification", "biometric liveness", "CKYC", "deepfake defense", "cryptographic audit"],
  openGraph: {
    title: "Identity Reconstruction — CKYC & Biometric Liveness",
    description: "Next-generation autonomous identity verification and deepfake defense platform.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <body className="antialiased" suppressHydrationWarning>
        {/* Customer-Facing Clean Header */}
        <header
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            zIndex: 50,
            backdropFilter: "blur(16px)",
            WebkitBackdropFilter: "blur(16px)",
            background: "rgba(5, 8, 17, 0.75)",
            borderBottom: "1px solid rgba(255, 255, 255, 0.07)",
            padding: "0.85rem 2rem",
          }}
        >
          <div
            style={{
              maxWidth: "1350px",
              margin: "0 auto",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            {/* Minimal Brand Logo */}
            <Link
              href="/"
              style={{
                textDecoration: "none",
                display: "flex",
                alignItems: "center",
                gap: "10px",
              }}
            >
              <div
                style={{
                  width: "30px",
                  height: "30px",
                  borderRadius: "8px",
                  background: "linear-gradient(135deg, #a855f7 0%, #06b6d4 100%)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: "14px",
                  boxShadow: "0 0 15px rgba(168, 85, 247, 0.4)",
                }}
              >
                ◈
              </div>
              <div style={{ display: "flex", flexDirection: "column" }}>
                <span
                  style={{
                    fontSize: "0.95rem",
                    fontWeight: 800,
                    letterSpacing: "0.08em",
                    textTransform: "uppercase",
                    background: "linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%)",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                  }}
                >
                  Identity Reconstruction
                </span>
                <span style={{ fontSize: "0.65rem", color: "#64748b", letterSpacing: "0.05em" }}>
                  SECURE IDENTITY PLATFORM
                </span>
              </div>
            </Link>

            {/* System Status & Clean Action */}
            <div style={{ display: "flex", alignItems: "center", gap: "1.25rem" }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "7px",
                  padding: "4px 12px",
                  borderRadius: "999px",
                  background: "rgba(16, 185, 129, 0.08)",
                  border: "1px solid rgba(16, 185, 129, 0.2)",
                  fontSize: "0.75rem",
                  color: "#10b981",
                  fontWeight: 600,
                  letterSpacing: "0.03em",
                }}
              >
                <span
                  style={{
                    width: "6px",
                    height: "6px",
                    borderRadius: "50%",
                    backgroundColor: "#10b981",
                    boxShadow: "0 0 8px #10b981",
                  }}
                />
                SYSTEM READY
              </div>

              <a
                href="#verification-hero"
                style={{
                  textDecoration: "none",
                  fontSize: "0.825rem",
                  fontWeight: 600,
                  color: "#ffffff",
                  background: "linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%)",
                  padding: "6px 16px",
                  borderRadius: "8px",
                  boxShadow: "0 0 15px rgba(124, 58, 237, 0.3)",
                  transition: "all 0.2s ease",
                }}
              >
                Start Verification →
              </a>
            </div>
          </div>
        </header>

        {/* Main Experience Body */}
        <main>{children}</main>

        {/* Discreet Customer Footer with Reviewer Portal Link */}
        <footer
          style={{
            borderTop: "1px solid rgba(255, 255, 255, 0.06)",
            background: "rgba(5, 8, 17, 0.95)",
            padding: "2.5rem 2rem",
            marginTop: "4rem",
          }}
        >
          <div
            style={{
              maxWidth: "1350px",
              margin: "0 auto",
              display: "flex",
              flexDirection: "row",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "1.5rem",
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <span style={{ fontSize: "0.85rem", fontWeight: 700, color: "#94a3b8" }}>
                Identity Reconstruction · Autonomous CKYC
              </span>
              <span style={{ fontSize: "0.75rem", color: "#475569" }}>
                ISO/IEC 30107-3 Liveness Compliant · Cryptographic SHA-256 Audit Chain · Zero Client Secret Exposure
              </span>
            </div>

            {/* Discreet, Low-Contrast Institution & Reviewer Link */}
            <div>
              <Link href="/review" className="footer-reviewer-link">
                <span>🔒</span> Institution / Reviewer Portal
              </Link>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
