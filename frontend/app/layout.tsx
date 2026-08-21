import type { Metadata } from "next";
import { Inter } from "next/font/google";
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
    <html lang="en" className={inter.variable}>
      <body className="antialiased">{children}</body>
    </html>
  );
}
