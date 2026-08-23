import type { Metadata } from "next";
import { Inter, Playfair_Display, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const playfair = Playfair_Display({
  subsets: ["latin"],
  variable: "--font-playfair",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  title: "ChainProof — Cinematic Identity Verification Platform",
  description:
    "Autonomous CKYC identity verification with wire-hashed archival, deterministic facial matching, and cryptographic hash chain sealing.",
  keywords: ["ChainProof", "identity verification", "CKYC", "biometric liveness", "cryptographic audit"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${playfair.variable} ${jetbrainsMono.variable}`} suppressHydrationWarning>
      <body className="antialiased font-sans" suppressHydrationWarning>
        {/* Minimal Customer Navigation */}
        <header
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            zIndex: 50,
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            background: "rgba(0, 0, 0, 0.75)",
            borderBottom: "1px solid rgba(39, 39, 42, 0.6)",
            padding: "1rem 2.5rem",
          }}
        >
          <div
            style={{
              maxWidth: "1400px",
              margin: "0 auto",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            {/* Left: ChainProof Minimal Logo */}
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
                  width: "16px",
                  height: "16px",
                  border: "1px solid #3B82F6",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <div style={{ width: "6px", height: "6px", backgroundColor: "#3B82F6" }} />
              </div>
              <span
                style={{
                  fontFamily: "var(--font-sans)",
                  fontSize: "0.95rem",
                  fontWeight: 600,
                  letterSpacing: "0.05em",
                  color: "#FFFFFF",
                  textTransform: "uppercase",
                }}
              >
                ChainProof
              </span>
            </Link>

            {/* Center/Right: Restrained Navigation */}
            <div style={{ display: "flex", alignItems: "center", gap: "2rem" }}>
              <a
                href="#how-it-works"
                style={{
                  color: "var(--text-muted)",
                  textDecoration: "none",
                  fontSize: "0.825rem",
                  fontWeight: 500,
                  transition: "color 0.15s ease",
                }}
              >
                How it works
              </a>
              <a
                href="#security"
                style={{
                  color: "var(--text-muted)",
                  textDecoration: "none",
                  fontSize: "0.825rem",
                  fontWeight: 500,
                  transition: "color 0.15s ease",
                }}
              >
                Security
              </a>
              <Link
                href="/onboarding"
                className="btn-primary-blue"
                style={{
                  padding: "0.5rem 1.25rem",
                  fontSize: "0.825rem",
                }}
              >
                Get Started →
              </Link>
            </div>
          </div>
        </header>

        {/* Main Experience */}
        <main>{children}</main>

        {/* Minimal Customer Footer */}
        <footer
          style={{
            borderTop: "1px solid var(--border-color)",
            background: "#000000",
            padding: "3rem 2.5rem",
            position: "relative",
            zIndex: 20,
          }}
        >
          <div
            style={{
              maxWidth: "1400px",
              margin: "0 auto",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: "1.5rem",
            }}
          >
            {/* Left Info */}
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <span style={{ fontSize: "0.9rem", fontWeight: 600, color: "#FFFFFF" }}>
                  ChainProof
                </span>
                <span style={{ fontSize: "0.8rem", color: "var(--text-dim)" }}>·</span>
                <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                  Identity Reconstruction · Deepfake-aware CKYC
                </span>
              </div>
              <span style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "var(--text-dim)" }}>
                Cryptographic SHA-256 Audit Chain · Multi-Stage Verification
              </span>
            </div>

            {/* Right: Discreet Reviewer Portal Route */}
            <div>
              <Link href="/review" className="footer-reviewer-link">
                <span>🔒</span> Institution / Reviewer Login →
              </Link>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
