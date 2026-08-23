import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Deepfake Agentic AI — Intelligent Deepfake Detection",
  description:
    "Upload any image or video and let our LangGraph-powered AI agent detect deepfakes with explainable, multi-step analysis.",
  keywords: ["deepfake detection", "AI", "LangGraph", "face analysis", "media forensics"],
  openGraph: {
    title: "Deepfake Agentic AI",
    description: "LangGraph-powered deepfake detection system",
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
        <header
          style={{
            position: "sticky",
            top: 0,
            zIndex: 50,
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            background: "rgba(15, 12, 41, 0.75)",
            borderBottom: "1px solid var(--border)",
            padding: "0.75rem 2rem",
          }}
        >
          <div
            style={{
              maxWidth: "1300px",
              margin: "0 auto",
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <Link
              href="/"
              style={{
                textDecoration: "none",
                fontWeight: 800,
                fontSize: "1.1rem",
                color: "white",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <span>🔍🤖</span>
              <span
                style={{
                  background: "linear-gradient(135deg, #f1f5f9 0%, #a855f7 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}
              >
                Deepfake Agentic AI
              </span>
            </Link>

            <nav style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
              <Link
                href="/"
                style={{
                  color: "var(--text-muted)",
                  textDecoration: "none",
                  fontSize: "0.875rem",
                  fontWeight: 600,
                  transition: "color 0.15s ease",
                }}
              >
                Analyze
              </Link>
              <Link
                href="/dashboard"
                style={{
                  color: "var(--text-muted)",
                  textDecoration: "none",
                  fontSize: "0.875rem",
                  fontWeight: 600,
                  transition: "color 0.15s ease",
                }}
              >
                Dashboard
              </Link>
              <Link
                href="/review"
                style={{
                  color: "var(--accent-2)",
                  textDecoration: "none",
                  fontSize: "0.875rem",
                  fontWeight: 600,
                  padding: "4px 10px",
                  borderRadius: "6px",
                  background: "rgba(6, 182, 212, 0.1)",
                  border: "1px solid rgba(6, 182, 212, 0.3)",
                }}
              >
                Review Portal
              </Link>
            </nav>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
