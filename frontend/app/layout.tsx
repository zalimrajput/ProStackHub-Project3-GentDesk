import type { Metadata } from "next";
import Link from "next/link";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "GentDesk — Autonomous Research Agent",
  description:
    "Multi-agent autonomous research platform: plan, search, evaluate, self-correct, synthesize.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body className="min-h-screen font-sans">
        {/* Ambient animated aurora background */}
        <div className="aurora-bg" aria-hidden="true">
          <div className="aurora-blob aurora-blob-1" />
          <div className="aurora-blob aurora-blob-2" />
          <div className="aurora-blob aurora-blob-3" />
          <div className="aurora-overlay" />
          <div className="aurora-vignette" />
        </div>

        <header className="sticky top-0 z-20 border-b border-white/5 bg-[#070812]/70 backdrop-blur-xl">
          <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
            <Link href="/" className="group flex items-center gap-2.5">
              <span className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 via-violet-500 to-fuchsia-600 text-sm font-bold text-white shadow-glow transition group-hover:shadow-glow-lg group-hover:brightness-110">
                G
                <span className="absolute -inset-px rounded-xl bg-gradient-to-br from-white/25 to-transparent opacity-0 transition group-hover:opacity-100" />
              </span>
              <span className="text-lg font-semibold tracking-tight text-white">
                GentDesk
                <span className="ml-2 hidden rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-normal uppercase tracking-wider text-slate-400 sm:inline">
                  Research Agent
                </span>
              </span>
            </Link>
            <nav className="flex items-center gap-1 text-sm">
              <Link
                href="/"
                className="rounded-lg px-3 py-1.5 text-slate-300 transition hover:bg-white/5 hover:text-white"
              >
                New Research
              </Link>
              <Link
                href="/#history"
                className="rounded-lg px-3 py-1.5 text-slate-300 transition hover:bg-white/5 hover:text-white"
              >
                History
              </Link>
            </nav>
          </div>
          <div className="shimmer-line" />
        </header>

        <main className="mx-auto max-w-6xl px-4 py-10">{children}</main>

        <footer className="border-t border-white/5 py-8">
          <div className="mx-auto flex max-w-6xl flex-col items-center gap-2 text-xs text-slate-500">
            <div className="flex items-center gap-2">
              {["Planner", "Research", "Evaluator", "Correction", "Synthesis"].map(
                (agent, i) => (
                  <span key={agent} className="flex items-center gap-2">
                    {i > 0 && <span className="text-slate-700">·</span>}
                    <span className="transition hover:text-slate-300">{agent}</span>
                  </span>
                ),
              )}
            </div>
            <p>GentDesk — Autonomous Research Agent</p>
          </div>
        </footer>
      </body>
    </html>
  );
}
