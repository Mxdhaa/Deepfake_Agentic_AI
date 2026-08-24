"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Navbar() {
  const pathname = usePathname();

  // Hide public marketing navbar entirely when inside authenticated/reviewer/dashboard tools
  if (pathname.startsWith("/review") || pathname.startsWith("/dashboard")) {
    return null;
  }

  return (
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
            href="/#how-it-works"
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
            href="/#security"
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
  );
}
