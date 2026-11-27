import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import ChangeBanner from "@/components/ChangeBanner";
import "./globals.css";

export const metadata: Metadata = {
  title: "F-1 Compliance Copilot",
  description: "Cited answers and deadline timelines for F-1 students. Information, not legal advice.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <div className="wrap header-row">
            <Link href="/" className="brand">
              F-1 Compliance Copilot
            </Link>
            <nav>
              <Link href="/">Ask</Link>
              <Link href="/timeline">My timeline</Link>
              <Link href="/sources">Rules &amp; sources</Link>
            </nav>
          </div>
        </header>
        <div className="disclaimer" role="note">
          <div className="wrap">
            An information tool, not legal advice. Always confirm with your school&apos;s
            Designated School Official (DSO) before acting.
          </div>
        </div>
        <main className="wrap">
          <ChangeBanner />
          {children}
        </main>
        <footer className="wrap footer">
          Answers come only from official sources and cite every sentence. Dates come from
          fixed, versioned rules, not AI.
        </footer>
      </body>
    </html>
  );
}
