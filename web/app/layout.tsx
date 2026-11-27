import type { Metadata, Viewport } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import type { ReactNode } from "react";
import ChangeBanner from "@/components/ChangeBanner";
import Footer from "@/components/Footer";
import Header from "@/components/Header";
import Providers from "@/components/Providers";
import SchoolPicker from "@/components/SchoolPicker";
import SkipLink from "@/components/SkipLink";
import "./globals.css";

const PLAUSIBLE = process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN;

const sans = Plus_Jakarta_Sans({ subsets: ["latin"], display: "swap", variable: "--font-sans" });

export const metadata: Metadata = {
  title: "F-1 Copilot",
  description:
    "Cited answers and deadline timelines for F-1 students at Big Ten schools and NYU. Information, not legal advice.",
};

export const viewport: Viewport = {
  colorScheme: "light",
  themeColor: "#F6F4EF",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={sans.variable}>
      <head>
        {PLAUSIBLE && (
          // Cookieless, anonymous page counts. Only loads when NEXT_PUBLIC_PLAUSIBLE_DOMAIN is set.
          <script defer data-domain={PLAUSIBLE} src="https://plausible.io/js/script.js" />
        )}
      </head>
      <body>
        <Providers>
          <SkipLink />
          <Header />
          <main className="wrap" id="main" tabIndex={-1}>
            <ChangeBanner />
            {children}
          </main>
          <Footer />
          <SchoolPicker />
        </Providers>
      </body>
    </html>
  );
}
