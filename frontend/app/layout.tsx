import type { Metadata } from "next";
import { Inter, Playfair_Display, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import Navbar from "@/components/Navbar";
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
        {/* Isolated Navigation Component */}
        <Navbar />

        {/* Main Route Content */}
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
                  Identity Reconstruction · Deepfake-aware KYC
                </span>
              </div>
              <span style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "var(--text-dim)" }}>
                Cryptographic SHA-256 Audit Chain · Multi-Stage Verification
              </span>
            </div>

            {/* Right: Clean Reviewer / Admin Login with NO emojis */}
            <div>
              <Link href="/review" className="footer-reviewer-link">
                Reviewer / Admin Login →
              </Link>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
